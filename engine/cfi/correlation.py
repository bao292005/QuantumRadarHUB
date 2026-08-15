"""Correlation spectral metrics — COPY VERBATIM from docs/02_ALGORITHM_SPEC.md.

DO NOT re-derive or "improve" the entropy formula (NFR1). Proven for 7/7 detection.
"""
import numpy as np
_EPS = 1e-12


def shrinkage_correlation(returns_by_asset: np.ndarray) -> np.ndarray:
    """Ledoit-Wolf shrinkage correlation. Input (N,T), output (N,N)."""
    x = np.asarray(returns_by_asset, dtype=float).T  # (T,N)
    if x.shape[0] < 2:
        raise ValueError("need >= 2 time observations")
    try:
        from sklearn.covariance import LedoitWolf
        cov = LedoitWolf(assume_centered=False).fit(x).covariance_
    except Exception:
        cov = np.cov(x, rowvar=False)
    d = np.sqrt(np.clip(np.diag(cov), _EPS, None))
    corr = cov / np.outer(d, d)
    np.fill_diagonal(corr, 1.0)
    return np.clip(corr, -1.0, 1.0)


def eigenvalue_entropy(corr: np.ndarray) -> float:
    """H = -1/ln N · Σ p_k ln p_k. LOW = concentrated = fragile. In [0,1]."""
    ev = np.clip(np.linalg.eigvalsh(corr), _EPS, None)
    p = ev / ev.sum()
    return float(-(p * np.log(p)).sum() / np.log(corr.shape[0]))


def max_eigenvalue(corr, *, normalize=True):
    lam = float(np.linalg.eigvalsh(corr).max())
    return lam / corr.shape[0] if normalize else lam


def average_strength(corr):
    n = corr.shape[0]; a = np.abs(corr).copy(); np.fill_diagonal(a, 0.0)
    return float(a.sum() / (n * (n - 1)))


def strong_edge_density(corr, *, rho=0.3):
    n = corr.shape[0]; a = np.abs(corr).copy(); np.fill_diagonal(a, 0.0)
    return float((a > rho).sum() / (n * (n - 1)))
