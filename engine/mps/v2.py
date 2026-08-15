"""MPS correlation score + RCS — COPY VERBATIM from docs/02_ALGORITHM_SPEC.md.

fragility = 1 - normalized_entropy(eigenvalues). HIGH = concentrated = crisis.
DO NOT invert the sign or truncate with chi<4 (Story 2.4 sweep: chi=None is optimal, NFR2).
"""
import numpy as np
from engine.cfi.correlation import shrinkage_correlation
_EPS = 1e-12


def _entropy_from_corr(C, chi):
    ev = np.linalg.eigvalsh(C); ev = np.clip(ev, _EPS, None)[::-1]  # descending
    if chi is not None and chi < len(ev): ev = ev[:chi]
    n = len(ev)
    if n <= 1: return 0.0
    p = np.clip(ev / ev.sum(), _EPS, 1.0)
    return float(-(p * np.log(p)).sum()) / np.log(n)


def mps_correlation_score(returns_window, *, chi=None):
    """(N,T) returns → fragility [0,1]. HIGH = concentrated = crisis."""
    R = np.asarray(returns_window, dtype=float)
    if R.ndim != 2: raise ValueError("returns_window must be 2-D")
    n, t = R.shape
    if n < 2 or t < 2: return 0.0
    mask = R.std(axis=1) > _EPS  # drop constant rows
    R = R[mask]
    if R.shape[0] < 2: return 0.0
    try: C = shrinkage_correlation(R)
    except Exception: return 0.0
    return 1.0 - _entropy_from_corr(C, chi)


def rcs_scores(returns_window, contract_labels=None, *, chi=None):
    """Leave-one-out risk contribution per contract."""
    R = np.asarray(returns_window, dtype=float); n = R.shape[0]
    labels = contract_labels or [str(i) for i in range(n)]
    full = mps_correlation_score(R, chi=chi)
    rcs = {lbl: full - mps_correlation_score(np.delete(R, i, axis=0), chi=chi)
           for i, lbl in enumerate(labels)}
    return dict(sorted(rcs.items(), key=lambda kv: kv[1], reverse=True))


def rolling_scores(returns, *, fit_window=40, score_stride=1, chi=None):
    """Score every rolling window."""
    R = np.asarray(returns, dtype=float); _, T = R.shape
    return [mps_correlation_score(R[:, t:t + fit_window], chi=chi)
            for t in range(0, T - fit_window + 1, score_stride)]
