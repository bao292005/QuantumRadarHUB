"""Shared validation pipeline — one code path for calibrate / sweep / gate.

Wraps the VERBATIM core (engine/*) with consistent windowing so all three tools
score fixtures identically. Uses the LOCKED constants from engine.scoring (NFR2).
"""
from engine.cfi.onchain import active_contracts, build_returns_matrix
from engine.mps.v2 import rolling_scores
from engine.scoring import FIT_WINDOW, WINDOW_BLOCKS, STRIDE_BLOCKS, CHI

# Matches the realtime detection path in docs/03_BUILD_GUIDE.md Phase 5.
MIN_WINDOWS_ACTIVE = 3
SECONDS_PER_BLOCK = 12.0


def fixture_returns(events):
    """(contracts, returns_matrix) for a fixture; returns (contracts, None) if too sparse."""
    contracts = active_contracts(
        events, min_windows_active=MIN_WINDOWS_ACTIVE,
        window_blocks=WINDOW_BLOCKS, stride_blocks=STRIDE_BLOCKS,
    )
    if len(contracts) < 2:
        return contracts, None
    R = build_returns_matrix(
        events, contracts, window_blocks=WINDOW_BLOCKS, stride_blocks=STRIDE_BLOCKS,
    )
    if R.shape[1] < 2:
        return contracts, None
    return contracts, R


def raw_rolling(events, *, fit_window=FIT_WINDOW, chi=CHI):
    """Time series of raw fragility [0,1] over the fixture (empty if insufficient)."""
    _, R = fixture_returns(events)
    if R is None or R.shape[1] < fit_window:
        return []
    return rolling_scores(R, fit_window=fit_window, chi=chi)


def window_end_blocks(events):
    """End block of each activity window — used to map a scored index to a block."""
    blocks = [e["block_number"] for e in events]
    if not blocks:
        return []
    lo, hi = blocks[0], blocks[-1]
    ends, b = [], lo + WINDOW_BLOCKS
    while b <= hi:
        ends.append(b)
        b += STRIDE_BLOCKS
    return ends


def scored_index_to_block(ends, i, *, fit_window=FIT_WINDOW):
    """Approx block at the end of scored window i (covers return-windows [i, i+fit_window))."""
    if not ends:
        return None
    idx = min(i + fit_window, len(ends) - 1)
    return ends[idx]
