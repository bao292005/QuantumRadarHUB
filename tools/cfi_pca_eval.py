"""Honest A/B: locked entropy detector vs experimental PCA-CFI (+ data cleaning).

Compares detection quality WITHOUT touching the locked core. Reports 7/7 crisis
detection and false-alarm rates for both, so any FP reduction (or 7/7 regression)
is visible. PCA-CFI is fitted on luna+normal reference windows; both detectors are
calibrated the same way (FLOOR=normal_max, CEIL=luna_p80).

    python3 -m tools.cfi_pca_eval
"""
import sys
from pathlib import Path

import numpy as np

from ingestion.csv_loader import load_events
from engine.mps.v2 import rolling_scores
from engine.scoring import SCORE_FLOOR, SCORE_CEIL, FIT_WINDOW
from engine.cfi.indicator import CFIModel, rolling_metrics
from tools._common import fixture_returns, window_end_blocks, scored_index_to_block
from tools.extract_fixtures import FIXTURES
from tools.honest_detection_count import CATEGORY

FIXTURE_DIR = Path("fixtures/backtest")
RED = 90.0
CRISES = [n for n, c in CATEGORY.items() if c == "crisis"]


def _score100(raw, floor, ceil):
    span = ceil - floor
    return 100.0 * max(0.0, min(1.0, (raw - floor) / span)) if span > 0 else 0.0


def _returns(name):
    path = FIXTURE_DIR / f"{name}.csv.gz"
    if not path.exists():
        return None, None, None
    events = load_events(str(path))
    contracts, R = fixture_returns(events)
    if R is None or R.shape[1] < FIT_WINDOW:
        return None, None, None
    return events, R, window_end_blocks(events)


def main():
    # --- fit PCA-CFI on luna + normal reference metric windows ---
    ref_metrics = []
    for name in ("luna_2022_05_09", "normal_2023_03_15"):
        _, R, _ = _returns(name)
        if R is not None:
            ref_metrics += [m for m in rolling_metrics(R) if m is not None]
    if len(ref_metrics) < 4:
        print("ERROR: need luna + normal extracted to fit PCA-CFI", file=sys.stderr)
        return 2
    model = CFIModel().fit(ref_metrics)
    print("PC1 loadings [avg_str, max_eig, strong_edge, entropy] =",
          np.round(model.w1, 3))

    # --- calibrate both detectors (FLOOR=normal_max, CEIL=luna_p80) ---
    def raws(name, which):
        _, R, _ = _returns(name)
        if R is None:
            return []
        if which == "entropy":
            return [x for x in rolling_scores(R, fit_window=FIT_WINDOW)]
        return [x for x in model.rolling_cfi(R) if not np.isnan(x)]

    luna_e, norm_e = raws("luna_2022_05_09", "entropy"), raws("normal_2023_03_15", "entropy")
    luna_p, norm_p = raws("luna_2022_05_09", "pca"), raws("normal_2023_03_15", "pca")
    floor_e, ceil_e = SCORE_FLOOR, SCORE_CEIL  # locked
    floor_p, ceil_p = float(np.max(norm_p)), float(np.percentile(luna_p, 80))
    print(f"PCA-CFI calib: FLOOR={floor_p:.4f} CEIL={ceil_p:.4f} "
          f"(FP-safe={'YES' if floor_p < ceil_p else 'NO'})\n")

    def detect(name):
        events, R, ends = _returns(name)
        if R is None:
            return None
        e_raw = list(rolling_scores(R, fit_window=FIT_WINDOW))
        p_raw = list(model.rolling_cfi(R))
        e = np.array([_score100(x, floor_e, ceil_e) for x in e_raw])
        p = np.array([_score100(0.0 if np.isnan(x) else x, floor_p, ceil_p) for x in p_raw])
        cascade = FIXTURES[name][2]
        def pre(scores):
            for i, s in enumerate(scores):
                if s >= RED:
                    blk = scored_index_to_block(ends, i)
                    if blk is not None and (cascade is None or blk <= cascade):
                        return True
            return False
        return {
            "cat": CATEGORY.get(name, "?"),
            "e_red": 100 * (e >= RED).mean(), "p_red": 100 * (p >= RED).mean(),
            "e_det": pre(e), "p_det": pre(p),
        }

    print(f"{'fixture':30} {'cat':11} {'OLD%RED':>8} {'NEW%RED':>8} {'OLDdet':>7} {'NEWdet':>7}")
    print("-" * 76)
    e_hit = p_hit = 0
    fp = {}
    for name in FIXTURES:
        d = detect(name)
        if d is None:
            continue
        crisis = d["cat"] == "crisis"
        if crisis:
            e_hit += d["e_det"]; p_hit += d["p_det"]
        if name in ("normal_2023_03_15", "busd_freeze_2023_02", "euler_hack_2023_03"):
            fp[name] = (d["e_red"], d["p_red"])
        edt = "✓" if d["e_det"] else ("-" if not crisis else "✗")
        pdt = "✓" if d["p_det"] else ("-" if not crisis else "✗")
        print(f"{name:30} {d['cat']:11} {d['e_red']:>7.0f}% {d['p_red']:>7.0f}% {edt:>7} {pdt:>7}")

    n_cris = sum(1 for n in FIXTURES if CATEGORY.get(n) == "crisis" and (FIXTURE_DIR / f"{n}.csv.gz").exists())
    print(f"\n=== GATE: crisis pre-cascade detected ===")
    print(f"  OLD (entropy)  : {e_hit}/{n_cris}")
    print(f"  NEW (PCA-CFI)  : {p_hit}/{n_cris}")
    print(f"\n=== FALSE ALARMS (%RED, lower=better) ===")
    print(f"  {'control':22} {'OLD':>6} {'NEW':>6}")
    for name, (e, p) in fp.items():
        print(f"  {name:22} {e:>5.0f}% {p:>5.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
