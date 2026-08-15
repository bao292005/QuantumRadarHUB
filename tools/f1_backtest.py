"""Rigorous F1 backtest on ONE continuous span (objective liq-cascade labels).

Protocol (defensible against a skeptical reviewer):
  * Data      : one long continuous block range (tools.extract_fixtures --from-block ...).
  * Labels    : forward liquidation-cascade (tools/labels.py) — objective, on-chain.
  * Samples   : each scoring window; CFI+MPS and B0 scored on the SAME windows.
  * Split     : TIME split with an embargo gap (= forward horizon). Positive-class AND
                detector thresholds are both chosen on TRAIN only.
  * Baseline  : B0 borrow-count scored identically → head-to-head F1.
  * Uncertainty: moving-block bootstrap 95% CI on the test timeline.

Honest finding: on this metric a volume baseline (B0) beats CFI+MPS — see
docs/09_F1_HONEST_FINDINGS.md. Exposed as compute_f1() for the dashboard.

    python3 -m tools.f1_backtest --span cont_q2_2022 [--horizon 48] [--pct 90]
"""
import argparse
import sys
from pathlib import Path

import numpy as np

from ingestion.csv_loader import load_events
from engine.scoring import score_100
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
    if not pairs:
        return None, 0.0
    best_thr, best_f1 = None, -1.0
    for t in sorted({s for s, _ in pairs}):
        f = _f1_at(pairs, t)
        if f >= best_f1:
            best_f1, best_thr = f, t
    return best_thr, best_f1


def _block_bootstrap_ci(pairs_in_time, thr, *, block=40, n=2000, seed=42):
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
    return [round(float(np.percentile(f1s, 2.5)), 3), round(float(np.percentile(f1s, 97.5)), 3)]


def compute_f1(span, *, horizon=48.0, pct=90.0, train_frac=0.4):
    """Run the continuous F1 backtest; return a structured result dict (or {'error': ...})."""
    path = FIXTURE_DIR / f"{span}.csv.gz"
    if not path.exists():
        return {"error": f"span not extracted: {span}"}
    events = load_events(str(path))
    contracts, R = fixture_returns(events)
    if R is None or R.shape[1] < 40:
        return {"error": "span too sparse to score"}

    cfi = [score_100(r) for r in rolling_scores(R, fit_window=40)]
    b0 = b0_scores(events)
    ends = window_end_blocks(events)
    scored_blocks = [scored_index_to_block(ends, i) for i in range(len(cfi))]
    counts = forward_liquidation_counts(events, scored_blocks, horizon_hours=horizon)

    n = min(len(cfi), len(b0), len(scored_blocks), len(counts))
    cfi, b0, scored_blocks, counts = cfi[:n], b0[:n], scored_blocks[:n], counts[:n]

    valid = [b for b in scored_blocks if b is not None]
    if not valid:
        return {"error": "no scored windows"}
    lo_b, hi_b = min(valid), max(valid)
    split_b = lo_b + train_frac * (hi_b - lo_b)
    embargo = int(horizon * 3600 / SECONDS_PER_BLOCK)

    train_idx = [i for i in range(n) if scored_blocks[i] is not None and scored_blocks[i] <= split_b]
    test_idx = [i for i in range(n) if scored_blocks[i] is not None and scored_blocks[i] >= split_b + embargo]

    liq_thr = percentile_threshold([counts[i] for i in train_idx], pct=pct)
    if liq_thr is None:
        return {"error": "no labelled train windows (span too short for this horizon)"}
    labels = labels_from_counts(counts, liq_thr)

    def _pairs(idx, scores):
        return [(scores[i], labels[i]) for i in idx if labels[i] is not None]

    tr_cfi, te_cfi = _pairs(train_idx, cfi), _pairs(test_idx, cfi)
    tr_b0, te_b0 = _pairs(train_idx, b0), _pairs(test_idx, b0)

    def _bal(pairs):
        pos = sum(1 for _, y in pairs if y == 1)
        return {"n": len(pairs), "pos": pos, "neg": len(pairs) - pos}

    if not te_cfi:
        return {"error": "empty test set"}

    detectors = []
    for name, tr, te in [("CFI+MPS", tr_cfi, te_cfi), ("B0 (borrow-count)", tr_b0, te_b0)]:
        thr, tr_f1 = _best_threshold(tr)
        tp, fp, fn, tn = _confusion(te, thr)
        p, r, f = _prf(tp, fp, fn)
        detectors.append({
            "name": name, "thr": round(thr, 3), "train_f1": round(tr_f1, 3),
            "precision": round(p, 3), "recall": round(r, 3), "test_f1": round(f, 3),
            "ci": _block_bootstrap_ci(te, thr),
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        })

    pr = []
    for t in range(0, 100, 10):
        tp, fp, fn, tn = _confusion(te_cfi, t)
        p, r, f = _prf(tp, fp, fn)
        pr.append({"thr": t, "precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)})

    delta = round(detectors[0]["test_f1"] - detectors[1]["test_f1"], 3)
    return {
        "span": span, "horizon": horizon, "pct": pct, "train_frac": train_frac,
        "liq_threshold": round(liq_thr, 1), "split_block": int(split_b), "embargo": embargo,
        "train": _bal(tr_cfi), "test": _bal(te_cfi),
        "detectors": detectors, "delta_f1": delta,
        "winner": "CFI+MPS" if delta > 0 else "B0 (borrow-count)",
        "pr_curve": pr,
    }


def _print_report(d):
    print(f"=== Rigorous F1 Backtest — span '{d['span']}' ===")
    print(f"labels: forward liquidation-cascade (>= P{d['pct']:.0f} of train count, horizon {d['horizon']:.0f}h)")
    print(f"liq-cascade threshold (from train): {d['liq_threshold']} liquidations / {d['horizon']:.0f}h")
    print(f"split @ block {d['split_block']}, embargo {d['embargo']} blocks")
    print(f"TRAIN: {d['train']['n']} windows ({d['train']['pos']} pos / {d['train']['neg']} neg)")
    print(f"TEST : {d['test']['n']} windows ({d['test']['pos']} pos / {d['test']['neg']} neg)\n")
    print(f"{'detector':20} {'thr*':>9} {'trainF1':>8} {'prec':>6} {'recall':>7} {'testF1':>7} {'95% CI':>15}")
    print("-" * 78)
    for r in d["detectors"]:
        ci = f"[{r['ci'][0]:.2f},{r['ci'][1]:.2f}]" if r["ci"] else "n/a"
        print(f"{r['name']:20} {r['thr']:>9.3f} {r['train_f1']:>8.3f} {r['precision']:>6.3f} "
              f"{r['recall']:>7.3f} {r['test_f1']:>7.3f} {ci:>15}")
    c = d["detectors"][0]
    print(f"\n→ CFI+MPS test F1 = {c['test_f1']} vs B0 = {d['detectors'][1]['test_f1']} (Δ = {d['delta_f1']:+})")
    cm = c["confusion"]
    print(f"  CFI+MPS confusion: TP={cm['tp']} FP={cm['fp']} FN={cm['fn']} TN={cm['tn']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rigorous F1 backtest on a continuous span")
    ap.add_argument("--span", required=True)
    ap.add_argument("--horizon", type=float, default=48.0)
    ap.add_argument("--pct", type=float, default=90.0)
    ap.add_argument("--train-frac", type=float, default=0.4)
    args = ap.parse_args(argv)
    d = compute_f1(args.span, horizon=args.horizon, pct=args.pct, train_frac=args.train_frac)
    if "error" in d:
        print(f"ERROR: {d['error']}", file=sys.stderr)
        return 2
    _print_report(d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
