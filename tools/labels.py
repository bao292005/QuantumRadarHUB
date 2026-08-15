"""Forward liquidation-cascade labels — objective ground truth for F1.

Stress = an actual liquidation cascade is coming. We label a scoring window POSITIVE
if the NUMBER of on-chain liquidation events in the next H hours is high (>= a
threshold). Count (not volume) is used deliberately: it is unit-free across assets
(USDC 6dec vs WETH 18dec vs WBTC 8dec are not comparable by raw amount) and directly
measures cascade breadth — how many positions got liquidated.

Detector looks at PAST/current correlation; label looks FORWARD → no leakage.
Windows without a full forward horizon are UNLABELLED (None) and excluded from F1.
The positive threshold is chosen on TRAIN only (see f1_backtest) to stay honest.
"""
import bisect

from tools._common import SECONDS_PER_BLOCK

_LIQUIDATION = "liquidation"


def _liquidation_blocks(events):
    return sorted(e["block_number"] for e in events if e.get("event_type") == _LIQUIDATION)


def forward_liquidation_counts(events, scored_blocks, *, horizon_hours=48.0):
    """Count liquidation events in (b, b+H] for each scored block; None if horizon incomplete."""
    if not events:
        return [None] * len(scored_blocks)
    liq = _liquidation_blocks(events)
    horizon_blocks = int(horizon_hours * 3600 / SECONDS_PER_BLOCK)
    max_block = events[-1]["block_number"]

    counts = []
    for b in scored_blocks:
        if b is None or b + horizon_blocks > max_block:
            counts.append(None)
            continue
        lo = bisect.bisect_right(liq, b)
        hi = bisect.bisect_right(liq, b + horizon_blocks)
        counts.append(hi - lo)
    return counts


def percentile_threshold(counts, *, pct=90.0, min_count=1):
    """Positive-class threshold from a set of forward counts (train only). >= min_count."""
    vals = sorted(c for c in counts if c is not None)
    if not vals:
        return None
    import numpy as np
    thr = float(np.percentile(vals, pct))
    return max(thr, float(min_count))


def labels_from_counts(counts, threshold):
    """Binarize forward counts at a fixed threshold; keep None as None."""
    if threshold is None:
        return [None for _ in counts]
    return [None if c is None else (1 if c >= threshold else 0) for c in counts]
