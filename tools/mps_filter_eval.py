"""MPS generative precision-filter — A/B on the entropy detector.

Gate: entropy_score >= 90 AND the window is out-of-distribution under an MPS density
model of NORMAL behaviour (anomaly = -log P above a percentile of the training set).
Only genuinely anomalous fragile windows fire → higher precision.

Training NOTE: a faithful "normal" model needs abundant clean-calm windows. Here we
train on cont_q2_2022 (2 months, mostly normal but contains luna+stETH) as a proxy —
re-train on the long calm spans (seg1-3) for the real model. Results below are a
mechanism demo; treat numbers as indicative until trained on clean calm data.

    python3 -m tools.mps_filter_eval
"""
import sys
from pathlib import Path

import numpy as np

from ingestion.csv_loader import load_events
from engine.mps.v2 import rolling_scores
from engine.scoring import SCORE_FLOOR, SCORE_CEIL, FIT_WINDOW
from engine.cfi.indicator import rolling_metrics
from engine.mps.generative import MPSBornDensity
from tools._common import fixture_returns, window_end_blocks, scored_index_to_block
from tools.extract_fixtures import FIXTURES
from tools.honest_detection_count import CATEGORY

FIXTURE_DIR = Path("fixtures/backtest")
RED = 90.0
TRAIN_SPAN = "cont_q2_2022"
PCTS = [50, 70, 80, 90, 95]
FP_FIXTURES = ["normal_2023_03_15", "busd_freeze_2023_02", "euler_hack_2023_03"]


def _score100(raw):
    span = SCORE_CEIL - SCORE_FLOOR
    return 100.0 * max(0.0, min(1.0, (raw - SCORE_FLOOR) / span))


def _returns(name):
    path = FIXTURE_DIR / f"{name}.csv.gz"
    if not path.exists():
        return None, None
    events = load_events(str(path))
    _, R = fixture_returns(events)
    if R is None or R.shape[1] < FIT_WINDOW:
        return None, None
    return R, window_end_blocks(events)


def main():
    R_tr, _ = _returns(TRAIN_SPAN)
    if R_tr is None:
        print(f"ERROR: training span {TRAIN_SPAN} not extracted", file=sys.stderr)
        return 2
    feats = np.array([m for m in rolling_metrics(R_tr) if m is not None])
    model = MPSBornDensity(n_bins=6, bond_dim=4).fit(feats)
    train_anom = np.array([model.anomaly(m) for m in feats])
    thr = {p: float(np.percentile(train_anom, p)) for p in PCTS}
    print(f"MPS trained on '{TRAIN_SPAN}' ({len(feats)} windows) — anomaly = -log P(normal)")
    print(f"anomaly percentiles: " + "  ".join(f"P{p}={thr[p]:.1f}" for p in PCTS) + "\n")

    data = {}
    for name in FIXTURES:
        R, ends = _returns(name)
        if R is None:
            continue
        e = np.array([_score100(x) for x in rolling_scores(R, fit_window=FIT_WINDOW)])
        mets = rolling_metrics(R)
        anom = np.array([model.anomaly(m) if m is not None else -np.inf for m in mets])
        n = min(len(e), len(anom))
        blocks = [scored_index_to_block(ends, i) for i in range(n)]
        data[name] = (e[:n], anom[:n], blocks, FIXTURES[name][2], CATEGORY.get(name, "?"))

    crises = [n for n, v in data.items() if v[4] == "crisis"]

    def evaluate(P):
        t = thr[P]
        hits, fp = 0, {}
        for name, (e, anom, blocks, cascade, cat) in data.items():
            red = (e >= RED) & (anom >= t)
            pre = any(red[i] and blocks[i] is not None and (cascade is None or blocks[i] <= cascade)
                      for i in range(len(red)))
            if cat == "crisis":
                hits += pre
            if name in FP_FIXTURES:
                fp[name] = 100.0 * red.mean()
        return hits, fp

    print(f"Gate: entropy>=90 AND anomaly>=P (OOD).  crises available: {len(crises)}/7\n")
    hdr = f"{'anomaly P':>10} {'crisis/7':>9} {'normal':>8} {'busd':>7} {'euler':>7}"
    print(hdr); print("-" * len(hdr))
    # baseline: entropy alone (no OOD gate)
    base_hits, base_fp = 0, {}
    for name, (e, anom, blocks, cascade, cat) in data.items():
        red = e >= RED
        pre = any(red[i] and blocks[i] is not None and (cascade is None or blocks[i] <= cascade)
                  for i in range(len(red)))
        if cat == "crisis":
            base_hits += pre
        if name in FP_FIXTURES:
            base_fp[name] = 100.0 * red.mean()
    print(f"{'(none)':>10} {base_hits:>7}/{len(crises)} "
          f"{base_fp.get('normal_2023_03_15',0):>7.0f}% {base_fp.get('busd_freeze_2023_02',0):>6.0f}% "
          f"{base_fp.get('euler_hack_2023_03',0):>6.0f}%")
    for P in PCTS:
        hits, fp = evaluate(P)
        print(f"{P:>10} {hits:>7}/{len(crises)} "
              f"{fp.get('normal_2023_03_15',0):>7.0f}% {fp.get('busd_freeze_2023_02',0):>6.0f}% "
              f"{fp.get('euler_hack_2023_03',0):>6.0f}%")
    print("\nHigher P = stricter OOD gate. Look for P keeping crisis=7/7 with lower FP.")
    print("⚠ trained on contaminated proxy — re-run after extracting clean calm spans.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
