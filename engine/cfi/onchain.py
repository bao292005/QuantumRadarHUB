"""On-chain activity/returns matrix builder — COPY VERBATIM from docs/02_ALGORITHM_SPEC.md.

Activity = Σ|amount0| per contract per window. DO NOT change window/stride defaults (NFR2).
"""
import bisect, numpy as np
from collections import defaultdict
_EPS = 1e-30


def _contract_activity(events, contract_addr):
    addr = contract_addr.lower(); total = 0.0
    for e in events:
        if e.get("pool_address", "").lower() == addr:
            try: total += abs(float(e.get("amount0") or 0))
            except (ValueError, TypeError): pass
    return total


def build_activity_matrix(events, contracts, *, window_blocks=300, stride_blocks=100):
    """(N_contracts × T_windows) raw activity volume."""
    if not events: return np.zeros((len(contracts), 0))
    blocks = [int(e["block_number"]) for e in events]
    lo, hi = blocks[0], blocks[-1]
    windows = []
    b = lo + window_blocks
    while b <= hi:
        li = bisect.bisect_left(blocks, b - window_blocks)
        ri = bisect.bisect_right(blocks, b)
        windows.append(events[li:ri]); b += stride_blocks
    if not windows: return np.zeros((len(contracts), 0))
    A = np.zeros((len(contracts), len(windows)))
    for j, win in enumerate(windows):
        for i, addr in enumerate(contracts):
            A[i, j] = _contract_activity(win, addr)
    return A


def build_returns_matrix(events, contracts, *, window_blocks=300, stride_blocks=100):
    """(N × T-1) log-returns of activity."""
    A = build_activity_matrix(events, contracts, window_blocks=window_blocks, stride_blocks=stride_blocks)
    if A.shape[1] < 2: return np.zeros((len(contracts), 0))
    A_safe = A + _EPS
    return np.log(A_safe[:, 1:] / A_safe[:, :-1])


def active_contracts(events, min_windows_active=5, **kw):
    """Contracts appearing in >= min_windows_active windows."""
    addrs = list({e.get("pool_address", "").lower() for e in events if e.get("pool_address")})
    if not addrs: return []
    A = build_activity_matrix(events, addrs, **kw)
    return [a for a, row in zip(addrs, A) if (row > 0).sum() >= min_windows_active]
