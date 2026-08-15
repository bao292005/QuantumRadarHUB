"""General backtest via F1 score over pooled scoring-windows (Epic 2 extension).

Unlike honest_detection_count (per-event 7/7), this treats EACH rolling window as a
classification sample and reports precision / recall / F1 across all fixtures — the
"would I trust it running 24/7" metric.

Labeling (objective, non-circular):
  positive  = window in a crisis fixture with block >= cascade - LEAD_MAX_HOURS
  negative  = every other window (calm run-up of crises + ALL fp_control fixtures)
  excluded  = near-miss fixtures (ambiguous ground truth) — reported separately

euler_hack stays all-negative on purpose: we do NOT claim to predict 1-block exploits,
so firing there is counted as a false positive (honest, deflates precision).

    python3 -m tools.honest... ; python3 -m tools.f1_backtest [--lead-hours 72] [--threshold 90]
"""
import argparse
import sys
from pathlib import Path

import numpy as np

from ingestion.csv_loader import load_events
from engine.scoring import score_100
from engine.mps.v2 import rolling_scores
from tools._common import (
    fixture_returns, window_end_blocks, scored_index_to_block, SECONDS_PER_BLOCK,
)
from tools.extract_fixtures import FIXTURES
from tools.honest_detection_count import CATEGORY

FIXTURE_DIR = Path("fixtures/backtest")


def _labelled_windows(name, lead_blocks):
    """Return list of (score, label) for one fixture, or None if not extracted."""
    path = FIXTURE_DIR / f"{name}.csv.gz"
    if not path.exists():
        return None
    events = load_events(str(path))
    _, R = fixture_returns(events)
    if R is None or R.shape[1] < 40:
        return []
    scores = [score_100(r) for r in rolling_scores(R, fit_window=40)]
    ends = window_end_blocks(events)
    cascade = FIXTURES[name][2]
    category = CATEGORY.get(name, "?")

    out = []
    for i, s in enumerate(scores):
        blk = scored_index_to_block(ends, i)
        positive = (
            category == "crisis" and cascade is not None
            and blk is not None and blk >= cascade - lead_blocks
        )
        out.append((s, 1 if positive else 0))
    return out


def _prf(tp, fp, fn):
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1


def main(argv=None):
    ap = argparse.ArgumentParser(description="F1 backtest over pooled scoring windows")
    ap.add_argument("--lead-hours", type=float, default=72.0,
                    help="hours before cascade still counted as positive (stress) zone")
    ap.add_argument("--threshold", type=float, default=90.0, help="RED threshold for the headline F1")
    args = ap.parse_args(argv)

    lead_blocks = int(args.lead_hours * 3600 / SECONDS_PER_BLOCK)

    pooled, per_fixture, missing, excluded = [], {}, [], {}
    for name in FIXTURES:
        w = _labelled_windows(name, lead_blocks)
        if w is None:
            missing.append(name)
            continue
        if CATEGORY.get(name) == "near_miss":
            excluded[name] = w
            continue
        per_fixture[name] = w
        pooled.extend(w)

    if not pooled:
        print("ERROR: no fixtures extracted — run tools.extract_fixtures first", file=sys.stderr)
        return 2

    scores = np.array([s for s, _ in pooled])
    labels = np.array([y for _, y in pooled])
    n_pos, n_neg = int(labels.sum()), int((labels == 0).sum())

    print(f"=== F1 Backtest (lead={args.lead_hours:.0f}h, {len(pooled)} windows, "
          f"{n_pos} pos / {n_neg} neg) ===\n")

    # Headline confusion matrix at the chosen threshold
    thr = args.threshold
    pred = scores >= thr
    tp = int((pred & (labels == 1)).sum())
    fp = int((pred & (labels == 0)).sum())
    fn = int((~pred & (labels == 1)).sum())
    tn = int((~pred & (labels == 0)).sum())
    prec, rec, f1 = _prf(tp, fp, fn)

    print(f"threshold = {thr:.0f} (RED)")
    print(f"  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"  precision={prec:.3f}  recall={rec:.3f}  F1={f1:.3f}\n")

    # Threshold sweep → F1-max
    print(f"{'thr':>5} {'prec':>7} {'recall':>7} {'F1':>7}")
    best = (0.0, None)
    for t in range(50, 100, 5):
        p = scores >= t
        _tp = int((p & (labels == 1)).sum())
        _fp = int((p & (labels == 0)).sum())
        _fn = int((~p & (labels == 1)).sum())
        pr, rc, ff = _prf(_tp, _fp, _fn)
        print(f"{t:>5} {pr:>7.3f} {rc:>7.3f} {ff:>7.3f}")
        if ff > best[0]:
            best = (ff, t)
    print(f"\n→ F1-max = {best[0]:.3f} at threshold {best[1]}")

    # Per-fixture FP contribution (which controls hurt precision)
    print("\n--- per-fixture @ RED (FP sources) ---")
    for name, w in per_fixture.items():
        s = np.array([x for x, _ in w]); y = np.array([yy for _, yy in w])
        red = s >= thr
        cat = CATEGORY.get(name)
        fp_here = int((red & (y == 0)).sum())
        tp_here = int((red & (y == 1)).sum())
        print(f"  {name:30} {cat:11} windows={len(w):4d} TP={tp_here:3d} FP={fp_here:3d}")

    if excluded:
        print("\n--- near-miss (excluded from F1, %RED for context) ---")
        for name, w in excluded.items():
            s = np.array([x for x, _ in w])
            print(f"  {name:30} %RED={100 * (s >= thr).mean():.0f}%")

    if missing:
        print(f"\n⚠ {len(missing)} fixtures not extracted — F1 is partial. Run extract --period all.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
