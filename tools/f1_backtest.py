"""Rigorous F1 backtest on ONE continuous span (objective liq-cascade labels).

Protocol (defensible against a skeptical reviewer):
  * Data      : one long continuous block range (tools.extract_fixtures --from-block ...).
  * Labels    : forward liquidation-cascade (tools/labels.py) — objective, on-chain,
                captures depeg cascades like LUNA that a price-drawdown label misses.
  * Samples   : each scoring window; CFI+MPS and B0 scored on the SAME windows.
  * Split     : TIME split with an embargo gap (= forward horizon) so train labels,
                which look forward, cannot peek into the test region. Positive-class
                threshold AND detector threshold are both chosen on TRAIN only.
  * Baseline  : B0 borrow-count scored identically → head-to-head F1.
  * Uncertainty: moving-block bootstrap 95% CI on the test timeline (windows are
                autocorrelated; contiguous blocks preserve that structure).

    python3 -m tools.f1_backtest --span cont_q2_2022 [--horizon 48] [--pct 90] [--train-frac 0.4]
"""
import argparse
import sys
from pathlib import Path

import numpy as np

from ingestion.csv_loader import load_events
from engine.scoring import score_100, STRIDE_BLOCKS
from engine.mps.v2 import rolling_scores
from tools._common import fixture_returns, window_end_blocks, scored_index_to_block, SECONDS_PER_BLOCK
from tools.baselines import b0_scores
from tools.labels import forward_liquidation_counts, percentile_threshold, labels_from_counts

FIXTURE_DIR = Path("fixtures/backtest")


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def _confusion(pairs, thr):
    tp = sum(1 for s, y in pairs if s >= thr and y == 1)
    fp = sum(1 for s, y in pairs if s >= thr and y == 0)
    fn = sum(1 for s, y in pairs if s < thr and y == 1)
    tn = sum(1 for s, y in pairs if s < thr and y == 0)
    return tp, fp, fn, tn


def _f1_at(pairs, thr):
    tp, fp, fn, _ = _confusion(pairs, thr)
    return _prf(tp, fp, fn)[2]


def _best_threshold(pairs):
    """Detector threshold maximizing F1 on TRAIN (tie → higher = more conservative)."""
    if not pairs:
        return None, 0.0
    best_thr, best_f1 = None, -1.0
    for t in sorted({s for s, _ in pairs}):
        f = _f1_at(pairs, t)
        if f >= best_f1:
            best_f1, best_thr = f, t
    return best_thr, best_f1


def _block_bootstrap_ci(pairs_in_time, thr, *, block=40, n=2000, seed=42):
    """Moving-block bootstrap 95% CI of F1 over a time-ordered pair list."""
    m = len(pairs_in_time)
    if m < 2 * block:
        return None
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(m / block))
    f1s = []
    for _ in range(n):
        idx = []
        for _b in range(n_blocks):
            start = int(rng.integers(0, m - block + 1))
            idx.extend(range(start, start + block))
        sample = [pairs_in_time[j] for j in idx[:m]]
        f1s.append(_f1_at(sample, thr))
    return float(np.percentile(f1s, 2.5)), float(np.percentile(f1s, 97.5))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rigorous F1 backtest on a continuous span")
    ap.add_argument("--span", required=True, help="continuous fixture name (fixtures/backtest/<span>.csv.gz)")
    ap.add_argument("--horizon", type=float, default=48.0, help="forward horizon hours for labels")
    ap.add_argument("--pct", type=float, default=90.0, help="percentile of TRAIN forward-counts = cascade")
    ap.add_argument("--train-frac", type=float, default=0.4, help="time fraction used for train")
    args = ap.parse_args(argv)

    path = FIXTURE_DIR / f"{args.span}.csv.gz"
    if not path.exists():
        print(f"ERROR: span not found: {path}", file=sys.stderr)
        print("  Extract one first, e.g.:", file=sys.stderr)
        print("  python3 -m tools.extract_fixtures --from-block 14700000 --to-block 15010000 "
              f"--name {args.span}", file=sys.stderr)
        return 2

    events = load_events(str(path))
    contracts, R = fixture_returns(events)
    if R is None or R.shape[1] < 40:
        print("ERROR: span too sparse to score.", file=sys.stderr)
        return 2

    cfi = [score_100(r) for r in rolling_scores(R, fit_window=40)]
    b0 = b0_scores(events)
    ends = window_end_blocks(events)
    scored_blocks = [scored_index_to_block(ends, i) for i in range(len(cfi))]
    counts = forward_liquidation_counts(events, scored_blocks, horizon_hours=args.horizon)

    n = min(len(cfi), len(b0), len(scored_blocks), len(counts))
    cfi, b0, scored_blocks, counts = cfi[:n], b0[:n], scored_blocks[:n], counts[:n]

    # --- TIME split with embargo (= forward horizon) so forward labels don't leak ---
    valid_blocks = [b for b in scored_blocks if b is not None]
    lo_b, hi_b = min(valid_blocks), max(valid_blocks)
    split_b = lo_b + args.train_frac * (hi_b - lo_b)
    embargo = int(args.horizon * 3600 / SECONDS_PER_BLOCK)

    train_idx = [i for i in range(n) if scored_blocks[i] is not None and scored_blocks[i] <= split_b]
    test_idx = [i for i in range(n) if scored_blocks[i] is not None and scored_blocks[i] >= split_b + embargo]

    # Positive-class threshold from TRAIN forward-counts only
    liq_thr = percentile_threshold([counts[i] for i in train_idx], pct=args.pct)
    if liq_thr is None:
        print("ERROR: no labelled train windows (increase span or lower horizon).", file=sys.stderr)
        return 2
    labels = labels_from_counts(counts, liq_thr)

    def _pairs(idx, scores):
        return [(scores[i], labels[i]) for i in idx if labels[i] is not None]

    tr_cfi, te_cfi = _pairs(train_idx, cfi), _pairs(test_idx, cfi)
    tr_b0, te_b0 = _pairs(train_idx, b0), _pairs(test_idx, b0)

    def _bal(pairs):
        pos = sum(1 for _, y in pairs if y == 1)
        return pos, len(pairs) - pos

    trp, trn = _bal(tr_cfi)
    tep, ten = _bal(te_cfi)

    print(f"=== Rigorous F1 Backtest — span '{args.span}' ===")
    print(f"labels: forward liquidation-cascade (>= P{args.pct:.0f} of train count, horizon {args.horizon:.0f}h)")
    print(f"liq-cascade threshold (from train): {liq_thr:.1f} liquidations / {args.horizon:.0f}h")
    print(f"split @ block {split_b:.0f}, embargo {embargo} blocks")
    print(f"TRAIN: {len(tr_cfi)} windows ({trp} pos / {trn} neg)")
    print(f"TEST : {len(te_cfi)} windows ({tep} pos / {ten} neg)\n")

    if not te_cfi or tep == 0:
        print("⚠ Test set has no positive labels — widen span or adjust horizon/pct.", file=sys.stderr)

    rows = []
    for name, tr, te in [("CFI+MPS", tr_cfi, te_cfi), ("B0 (borrow-count)", tr_b0, te_b0)]:
        thr, tr_f1 = _best_threshold(tr)
        tp, fp, fn, tn = _confusion(te, thr)
        p, r, f = _prf(tp, fp, fn)
        ci = _block_bootstrap_ci(te, thr)
        rows.append((name, thr, tr_f1, p, r, f, ci, (tp, fp, fn, tn)))

    print(f"{'detector':20} {'thr*':>9} {'trainF1':>8} {'prec':>6} {'recall':>7} {'testF1':>7} {'95% CI':>15}")
    print("-" * 78)
    for name, thr, trf, p, r, f, ci, cm in rows:
        ci_s = f"[{ci[0]:.2f},{ci[1]:.2f}]" if ci else "n/a"
        print(f"{name:20} {thr:>9.3f} {trf:>8.3f} {p:>6.3f} {r:>7.3f} {f:>7.3f} {ci_s:>15}")

    cfi_f1, b0_f1 = rows[0][5], rows[1][5]
    tp, fp, fn, tn = rows[0][7]
    print(f"\n→ CFI+MPS test F1 = {cfi_f1:.3f}  vs  B0 = {b0_f1:.3f}  (Δ = {cfi_f1 - b0_f1:+.3f})")
    print(f"  CFI+MPS confusion: TP={tp} FP={fp} FN={fn} TN={tn}")

    print(f"\n--- CFI+MPS PR curve on TEST ---")
    print(f"{'thr':>6} {'prec':>7} {'recall':>7} {'F1':>7}")
    for t in range(0, 100, 10):
        tp, fp, fn, tn = _confusion(te_cfi, t)
        p, r, f = _prf(tp, fp, fn)
        print(f"{t:>6} {p:>7.3f} {r:>7.3f} {f:>7.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
