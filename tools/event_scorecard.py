"""Fair event-level scorecard — CFI+MPS vs B0 under an identical protocol.

Rare-event detection judged fairly (not by volume F1):
  * Fixed threshold (RED=90) with the SAME calibration for both detectors
    (FLOOR = normal_max, CEIL = luna_p80 of each detector's own raw score).
  * In-sample (luna, used to calibrate) reported separately from out-of-sample crises.
  * Alert-budget significance: given a detector's calm-market RED rate p, what is the
    chance it catches every crisis pre-cascade BY LUCK? P(all) = ∏ (1-(1-p)^W_e).
    This credits a rare-but-accurate detector and discounts a trigger-happy one —
    the objective equalizer vs a high-recall baseline that just fires a lot.
  * False-alarm rate on the calm control; event-level bootstrap CI.

Everything is applied identically to CFI+MPS and B0. Edge cases disclosed.

    python3 -m tools.event_scorecard
"""
import sys
from pathlib import Path

import numpy as np

from ingestion.csv_loader import load_events
from engine.mps.v2 import rolling_scores
from engine.scoring import FIT_WINDOW
from tools._common import fixture_returns, window_end_blocks, scored_index_to_block, SECONDS_PER_BLOCK
from tools.baselines import b0_scores
from tools.extract_fixtures import FIXTURES
from tools.honest_detection_count import CATEGORY

FIXTURE_DIR = Path("fixtures/backtest")
RED = 90.0
LEAD_HOURS = 72.0
CALM = "normal_2023_03_15"          # short clean-calm control (calibration reference)
CALM_SPAN = "calm_jun_2023"          # LONG calm span for a real alert-budget estimate
IN_SAMPLE = "luna_2022_05_09"        # used for calibration → reported separately
CRISES = [n for n, c in CATEGORY.items() if c == "crisis"]
EDGE = ["busd_freeze_2023_02", "euler_hack_2023_03", "crv_near_miss_2023_08", "crv_near_miss_2023_11"]


def _raw(name, which):
    path = FIXTURE_DIR / f"{name}.csv.gz"
    if not path.exists():
        return None, None
    events = load_events(str(path))
    contracts, R = fixture_returns(events)
    if R is None or R.shape[1] < FIT_WINDOW:
        return None, None
    ends = window_end_blocks(events)
    if which == "entropy":
        scores = list(rolling_scores(R, fit_window=FIT_WINDOW))
    else:
        scores = list(b0_scores(events))
    blocks = [scored_index_to_block(ends, i) for i in range(len(scores))]
    return np.array(scores), blocks


def _s100(raw, floor, ceil):
    span = ceil - floor
    return 100.0 * np.clip((raw - floor) / span, 0, 1) if span > 0 else np.zeros_like(raw)


def scorecard(which, label):
    lead_blocks = int(LEAD_HOURS * 3600 / SECONDS_PER_BLOCK)
    luna_raw, _ = _raw(IN_SAMPLE, which)
    norm_raw, _ = _raw(CALM, which)
    if luna_raw is None or norm_raw is None:
        return None
    floor, ceil = float(np.max(norm_raw)), float(np.percentile(luna_raw, 80))

    # alert budget p on the LONG calm span (falls back to the short control if absent)
    budget_raw, _ = _raw(CALM_SPAN, which)
    budget_name = CALM_SPAN
    if budget_raw is None:
        budget_raw, budget_name = norm_raw, CALM
    b_s = _s100(budget_raw, floor, ceil)
    red_b = int((b_s >= RED).sum())
    p = (red_b + 0.5) / (len(b_s) + 1.0)          # Laplace-smoothed
    fa_rate = 100.0 * (b_s >= RED).mean()

    results = {"floor": floor, "ceil": ceil, "p": p, "fa_rate": fa_rate,
               "budget_name": budget_name, "budget_windows": len(b_s)}
    hits_oos, leads, W = [], [], []
    for name in CRISES:
        raw, blocks = _raw(name, which)
        if raw is None:
            continue
        s = _s100(raw, floor, ceil)
        cascade = FIXTURES[name][2]
        zone = [i for i in range(len(s)) if blocks[i] is not None
                and cascade - lead_blocks <= blocks[i] <= cascade]
        hit = any(s[i] >= RED for i in zone)
        lead = None
        for i in zone:
            if s[i] >= RED:
                lead = (cascade - blocks[i]) * SECONDS_PER_BLOCK / 3600.0
                break
        if name == IN_SAMPLE:
            results["luna_hit"] = hit
            results["luna_lead"] = lead
        else:
            hits_oos.append(1 if hit else 0)
            if lead is not None:
                leads.append(lead)
            W.append(len(zone))
    results["oos_hits"] = sum(hits_oos)
    results["oos_n"] = len(hits_oos)
    results["median_lead"] = float(np.median(leads)) if leads else None
    # null probability of catching all OOS crises by chance at budget p
    null = 1.0
    for w in W:
        null *= (1.0 - (1.0 - p) ** w)
    results["null_prob"] = null
    # event bootstrap CI on OOS recall
    if hits_oos:
        rng = np.random.default_rng(42)
        boot = [np.mean(rng.choice(hits_oos, len(hits_oos), replace=True)) for _ in range(2000)]
        results["recall_ci"] = (round(float(np.percentile(boot, 2.5)), 2),
                                round(float(np.percentile(boot, 97.5)), 2))
    # edge cases (disclosure): %RED
    edge = {}
    for name in EDGE:
        raw, _ = _raw(name, which)
        if raw is not None:
            edge[name] = 100.0 * (_s100(raw, floor, ceil) >= RED).mean()
    results["edge"] = edge
    return results


def main():
    cfi = scorecard("entropy", "CFI+MPS")
    b0 = scorecard("b0", "B0")
    if cfi is None or b0 is None:
        print("ERROR: need luna + normal extracted", file=sys.stderr); return 2

    def row(k, fmt, cf, bf):
        print(f"  {k:34} {fmt(cf):>14} {fmt(bf):>14}")

    print("=== FAIR EVENT-LEVEL SCORECARD (fixed RED=90, identical protocol) ===")
    print(f"lead window {LEAD_HOURS:.0f}h | in-sample={IN_SAMPLE}")
    print(f"alert budget from '{cfi['budget_name']}' ({cfi['budget_windows']} windows)"
          + ("  ⚠ short control — extract a long calm span for a real budget"
             if cfi["budget_name"] == CALM else "  ✓ long calm span") + "\n")
    print(f"  {'metric':34} {'CFI+MPS':>14} {'B0':>14}")
    print("  " + "-" * 62)
    row("alert budget p (calm RED rate)", lambda d: f"{d['p']*100:.1f}%", cfi, b0)
    row("false-alarm rate on normal", lambda d: f"{d['fa_rate']:.0f}%", cfi, b0)
    row("crises caught OOS", lambda d: f"{d['oos_hits']}/{d['oos_n']}", cfi, b0)
    row("  luna (in-sample)", lambda d: f"{'hit' if d.get('luna_hit') else 'miss'}", cfi, b0)
    row("median lead time (h)", lambda d: f"{d['median_lead']:.1f}" if d['median_lead'] else "-", cfi, b0)
    row("OOS recall 95% CI", lambda d: f"{d.get('recall_ci','-')}", cfi, b0)
    row("null P(catch all OOS by luck)", lambda d: f"{d['null_prob']:.2e}", cfi, b0)
    print()
    print("  → Lower null-P at LOWER alert budget = stronger skill-beyond-firing-rate.")
    print("\n  Edge cases (disclosed, %RED — not scored as clean):")
    for name in EDGE:
        c = cfi["edge"].get(name); b = b0["edge"].get(name)
        if c is not None:
            print(f"    {name:30} CFI {c:>4.0f}%   B0 {b:>4.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
