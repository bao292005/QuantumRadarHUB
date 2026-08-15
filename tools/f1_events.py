"""Event-level pooled F1 across discrete fixtures (CFI+MPS vs B0), with --exclude.

Complements the continuous F1 (tools/f1_backtest.py). Here each scoring window across
the crisis/control fixtures is a sample; positive = window in a crisis fixture within
LEAD_HOURS before its cascade block. Controls are all-negative. near-miss fixtures are
skipped (ambiguous). Threshold is each detector's own best-F1 (in-sample, same for both
→ fair head-to-head). Labels are cascade-based (event-detection eval), not p80.

    python3 -m tools.f1_events
    python3 -m tools.f1_events --exclude ftx_2022_11_08,busd_freeze_2023_02,euler_hack_2023_03
"""
import argparse
from pathlib import Path

from ingestion.csv_loader import load_events
from engine.scoring import score_100
from engine.mps.v2 import rolling_scores
from tools._common import fixture_returns, window_end_blocks, scored_index_to_block, SECONDS_PER_BLOCK
from tools.baselines import b0_scores
from tools.extract_fixtures import FIXTURES
from tools.honest_detection_count import CATEGORY

FIXTURE_DIR = Path("fixtures/backtest")


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def _f1_at(pairs, thr):
    tp = sum(1 for s, y in pairs if s >= thr and y == 1)
    fp = sum(1 for s, y in pairs if s >= thr and y == 0)
    fn = sum(1 for s, y in pairs if s < thr and y == 1)
    return _prf(tp, fp, fn)


def _best(pairs):
    best = (-1.0, None, 0.0, 0.0)
    for t in sorted({s for s, _ in pairs}):
        p, r, f = _f1_at(pairs, t)
        if f > best[0]:
            best = (f, t, p, r)
    return best  # f1, thr, prec, recall


def main(argv=None):
    ap = argparse.ArgumentParser(description="Event-level pooled F1 with exclusions")
    ap.add_argument("--lead-hours", type=float, default=72.0)
    ap.add_argument("--exclude", default="", help="comma-separated fixture names to drop")
    args = ap.parse_args(argv)
    exclude = {x.strip() for x in args.exclude.split(",") if x.strip()}
    lead_blocks = int(args.lead_hours * 3600 / SECONDS_PER_BLOCK)

    cfi_pool, b0_pool = [], []
    used, skipped = [], []
    for name in FIXTURES:
        if name in exclude:
            skipped.append(name); continue
        cat = CATEGORY.get(name, "custom")
        if cat == "near_miss":
            continue
        path = FIXTURE_DIR / f"{name}.csv.gz"
        if not path.exists():
            continue
        events = load_events(str(path))
        contracts, R = fixture_returns(events)
        if R is None or R.shape[1] < 40:
            continue
        cfi = [score_100(r) for r in rolling_scores(R, fit_window=40)]
        b0 = b0_scores(events)
        ends = window_end_blocks(events)
        cascade = FIXTURES[name][2]
        n = min(len(cfi), len(b0))
        for i in range(n):
            blk = scored_index_to_block(ends, i)
            label = 1 if (cat == "crisis" and cascade is not None and blk is not None
                          and blk >= cascade - lead_blocks) else 0
            cfi_pool.append((cfi[i], label)); b0_pool.append((b0[i], label))
        used.append(name)

    pos = sum(1 for _, y in cfi_pool if y == 1)
    print(f"=== Event-level pooled F1 (lead {args.lead_hours:.0f}h) ===")
    if exclude:
        print(f"excluded: {', '.join(sorted(exclude))}")
    print(f"fixtures used: {len(used)} | windows: {len(cfi_pool)} ({pos} pos / {len(cfi_pool)-pos} neg)\n")

    cf1, ct, cp, cr = _best(cfi_pool)
    bf1, bt, bp, br = _best(b0_pool)
    p90, r90, f90 = _f1_at(cfi_pool, 90)

    print(f"{'detector':20} {'thr*':>7} {'prec':>6} {'recall':>7} {'F1':>7}")
    print("-" * 52)
    print(f"{'CFI+MPS (best)':20} {ct:>7.1f} {cp:>6.3f} {cr:>7.3f} {cf1:>7.3f}")
    print(f"{'CFI+MPS @90':20} {90:>7.1f} {p90:>6.3f} {r90:>7.3f} {f90:>7.3f}")
    print(f"{'B0 (best)':20} {bt:>7.1f} {bp:>6.3f} {br:>7.3f} {bf1:>7.3f}")
    print(f"\n→ CFI+MPS F1={cf1:.3f} vs B0 F1={bf1:.3f} (Δ={cf1 - bf1:+.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
