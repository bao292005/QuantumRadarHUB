"""Honest detection count — the 7/7 gate (Story 2.5, FR13).

Uses FIXED thresholds (YELLOW=70, RED=90) on the calibrated [0,100] score — NOT
p80-per-scenario (that is circular/fake, docs/05_RESULTS.md). Reports mean, %RED,
pre-cascade lead time, and RCS top contributors per fixture.

PASS = 7/7 crisis detected @ RED before cascade  AND  normal == 0% RED.

    python3 -m tools.honest_detection_count
"""
import sys
from pathlib import Path

import numpy as np

from ingestion.csv_loader import load_events
from engine.scoring import score_100
from engine.mps.v2 import rolling_scores, rcs_scores
from tools._common import (
    fixture_returns, window_end_blocks, scored_index_to_block, SECONDS_PER_BLOCK,
)
from tools.extract_fixtures import FIXTURES

FIXTURE_DIR = Path("fixtures/backtest")
RED = 90.0
YELLOW = 70.0

# Category per fixture (docs/05_RESULTS.md). CRISIS set defines the 7/7 gate.
CATEGORY = {
    "luna_2022_05_09": "crisis",
    "ftx_2022_11_08": "crisis",
    "steth_depeg_2022_06": "crisis",
    "may_2021_eth_crash": "crisis",
    "wbtc_cascade_2022_06": "crisis",
    "eth_cascade_ftx_week_2022_11": "crisis",
    "usdc_depeg_2023_03": "crisis",
    "normal_2023_03_15": "fp_control",
    "busd_freeze_2023_02": "fp_control",
    "euler_hack_2023_03": "fp_control",
    "crv_near_miss_2023_08": "near_miss",
    "crv_near_miss_2023_11": "near_miss",
}


def analyze(name):
    path = FIXTURE_DIR / f"{name}.csv.gz"
    if not path.exists():
        return None
    events = load_events(str(path))
    contracts, R = fixture_returns(events)
    if R is None or R.shape[1] < 40:
        return {"name": name, "missing": False, "insufficient": True}

    raws = rolling_scores(R, fit_window=40)
    scores = np.array([score_100(r) for r in raws])
    ends = window_end_blocks(events)
    cascade = FIXTURES[name][2]

    mean_s = float(scores.mean())
    pct_red = float((scores >= RED).mean() * 100.0)

    detected, lead_h = False, None
    if cascade is not None:
        for i, s in enumerate(scores):
            if s >= RED:
                blk = scored_index_to_block(ends, i)
                if blk is not None and blk <= cascade:
                    detected, lead_h = True, (cascade - blk) * SECONDS_PER_BLOCK / 3600.0
                    break

    # RCS top-3 at peak-score window
    rcs_top = []
    if len(scores):
        i_star = int(scores.argmax())
        window = R[:, i_star:i_star + 40]
        if window.shape[1] >= 2 and scores[i_star] >= 50:
            rcs = rcs_scores(window, contracts)
            rcs_top = [lbl[:10] for lbl in list(rcs)[:3]]

    return {
        "name": name, "missing": False, "insufficient": False,
        "category": CATEGORY.get(name, "?"),
        "mean": mean_s, "pct_red": pct_red,
        "detected": detected, "lead_h": lead_h, "rcs_top": rcs_top,
    }


def main():
    results, missing = [], []
    for name in FIXTURES:
        r = analyze(name)
        if r is None:
            missing.append(name)
        else:
            results.append(r)

    print("=== Honest Detection Count (FIXED threshold RED=90 / YELLOW=70) ===\n")
    hdr = f"{'fixture':30} {'category':11} {'mean':>6} {'%RED':>6} {'lead(h)':>8} {'detect':>7}"
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        if r.get("insufficient"):
            print(f"{r['name']:30} {'(insufficient data)':>0}")
            continue
        lead = f"{r['lead_h']:.1f}" if r["lead_h"] is not None else "-"
        det = "✓" if r["detected"] else ("-" if r["category"] != "crisis" else "✗")
        print(f"{r['name']:30} {r['category']:11} {r['mean']:>6.1f} {r['pct_red']:>5.0f}% {lead:>8} {det:>7}")

    crises = [r for r in results if r.get("category") == "crisis" and not r.get("insufficient")]
    detected = [r for r in crises if r["detected"]]
    normal = next((r for r in results if r.get("name") == "normal_2023_03_15"), None)

    print("\n=== GATE ===")
    print(f"Crisis detected @ RED (pre-cascade): {len(detected)}/{len(crises)}"
          + (f" (of 7 expected)" if len(crises) < 7 else ""))
    if normal and not normal.get("insufficient"):
        print(f"FP control clean: normal = {normal['pct_red']:.0f}% RED")

    # RCS evidence
    print("\n--- RCS top contributors (peak window) ---")
    for r in crises:
        if r.get("rcs_top"):
            print(f"  {r['name']:30} → {', '.join(r['rcs_top'])}")

    if missing:
        print(f"\n⚠ {len(missing)} fixtures not extracted: {', '.join(missing)}")
        print("  Run: python3 -m tools.extract_fixtures --period all")

    gate_pass = (len(crises) == 7 and len(detected) == 7
                 and normal is not None and not normal.get("insufficient")
                 and normal["pct_red"] == 0.0)
    print(f"\nRESULT: {'✅ PASS (7/7 + 0% FP)' if gate_pass else '❌ NOT YET (see above)'}")
    return 0 if gate_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
