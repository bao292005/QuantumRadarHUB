"""Ensemble A/B: entropy detector gated by PCA-CFI confirmation.

Ensemble RED = (entropy_score >= 90) AND (pca_cfi_score >= G). The entropy detector
supplies recall (catches all 7, incl. spiky ones); PCA-CFI is quiet on the false-alarm
fixtures (busd/euler/crv) so requiring it to confirm filters those FPs. We sweep the
gate G and print the full recall/FP tradeoff (transparent — no single cherry-picked G).

    python3 -m tools.cfi_ensemble_eval
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
GATES = [0, 5, 10, 20, 30, 40, 50, 70]
FP_FIXTURES = ["normal_2023_03_15", "busd_freeze_2023_02", "euler_hack_2023_03"]


def _score100(raw, floor, ceil):
    span = ceil - floor
    return 100.0 * max(0.0, min(1.0, (raw - floor) / span)) if span > 0 else 0.0


def _returns(name):
    path = FIXTURE_DIR / f"{name}.csv.gz"
    if not path.exists():
        return None, None
    events = load_events(str(path))
    contracts, R = fixture_returns(events)
    if R is None or R.shape[1] < FIT_WINDOW:
        return None, None
    return R, window_end_blocks(events)


def main():
    ref = []
    for name in ("luna_2022_05_09", "normal_2023_03_15"):
        R, _ = _returns(name)
        if R is not None:
            ref += [m for m in rolling_metrics(R) if m is not None]
    if len(ref) < 4:
        print("ERROR: need luna + normal", file=sys.stderr); return 2
    model = CFIModel().fit(ref)

    def pca_raws(name):
        R, _ = _returns(name)
        return [] if R is None else [x for x in model.rolling_cfi(R) if not np.isnan(x)]
    floor_p = float(np.max(pca_raws("normal_2023_03_15")))
    ceil_p = float(np.percentile(pca_raws("luna_2022_05_09"), 80))

    # precompute per-fixture aligned e/p score arrays + blocks
    data = {}
    for name in FIXTURES:
        R, ends = _returns(name)
        if R is None:
            continue
        e = np.array([_score100(x, SCORE_FLOOR, SCORE_CEIL) for x in rolling_scores(R, fit_window=FIT_WINDOW)])
        p = np.array([_score100(0.0 if np.isnan(x) else x, floor_p, ceil_p) for x in model.rolling_cfi(R)])
        n = min(len(e), len(p))
        blocks = [scored_index_to_block(ends, i) for i in range(n)]
        data[name] = (e[:n], p[:n], blocks, FIXTURES[name][2], CATEGORY.get(name, "?"))

    crises = [n for n, v in data.items() if v[4] == "crisis"]

    def evaluate(G):
        hits = 0
        fp = {}
        for name, (e, p, blocks, cascade, cat) in data.items():
            red = (e >= RED) & (p >= G)
            pre = any(red[i] and blocks[i] is not None and (cascade is None or blocks[i] <= cascade)
                      for i in range(len(red)))
            if cat == "crisis" and pre:
                hits += 1
            if name in FP_FIXTURES:
                fp[name] = 100.0 * red.mean()
        return hits, fp

    print(f"Ensemble: entropy>=90 AND PCA-CFI>=G   (PCA calib FLOOR={floor_p:.3f} CEIL={ceil_p:.3f})")
    print(f"crises available: {len(crises)}/7\n")
    hdr = f"{'gate G':>7} {'crisis/7':>9} {'normal':>8} {'busd':>7} {'euler':>7}"
    print(hdr); print("-" * len(hdr))
    for G in GATES:
        hits, fp = evaluate(G)
        print(f"{G:>7} {hits:>7}/{len(crises)} "
              f"{fp.get('normal_2023_03_15',0):>7.0f}% {fp.get('busd_freeze_2023_02',0):>6.0f}% "
              f"{fp.get('euler_hack_2023_03',0):>6.0f}%")
    print("\nG=0 → entropy alone (baseline). Higher G → PCA-CFI confirmation filters FPs.")
    print("Pick the largest G that still keeps crisis=7/7 (lowest FP without losing recall).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
