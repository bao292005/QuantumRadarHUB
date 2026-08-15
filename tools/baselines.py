"""B0 baseline detector — borrow/liquidation event count per window.

The naive "just count leverage activity" approach CFI+MPS is meant to beat. Produces
one score per scoring window, index-aligned to engine rolling_scores, so the same F1
protocol can score both detectors head-to-head.
"""
import bisect

from engine.scoring import WINDOW_BLOCKS, STRIDE_BLOCKS, FIT_WINDOW

_LEVERAGE_EVENTS = {"borrow", "liquidation"}


def _activity_window_counts(events):
    """Count leverage events per activity window (same windowing as build_activity_matrix)."""
    if not events:
        return []
    blocks = [e["block_number"] for e in events]
    lo, hi = blocks[0], blocks[-1]
    counts, b = [], lo + WINDOW_BLOCKS
    while b <= hi:
        li = bisect.bisect_left(blocks, b - WINDOW_BLOCKS)
        ri = bisect.bisect_right(blocks, b)
        c = sum(1 for e in events[li:ri] if e.get("event_type") in _LEVERAGE_EVENTS)
        counts.append(c)
        b += STRIDE_BLOCKS
    return counts


def b0_scores(events, *, fit_window=FIT_WINDOW):
    """Per scored-window B0 score = mean leverage-event count over its fit_window span.

    Length matches rolling_scores(returns, fit_window): T_activity_windows - fit_window.
    """
    counts = _activity_window_counts(events)
    T = len(counts)
    if T <= fit_window:
        return []
    out = []
    for i in range(0, T - fit_window):
        span = counts[i:i + fit_window + 1]
        out.append(sum(span) / len(span))
    return out
