"""PCA-CFI — the full 4-metric Correlation Fragility Indicator (arXiv:2601.08540 §IV).

The locked detector (engine/mps/v2.py) uses only ONE of the paper's four correlation
metrics (eigenvalue entropy). Here we implement the paper's actual CFI: four
complementary spectral/network metrics fused into a single index via PCA (first
principal component). This is an experimental upgrade — compared against the locked
entropy detector, never replacing it (7/7 gate stays on the verbatim core).

Metrics per window (all from engine/cfi/correlation.py):
  0 average_strength    — system-wide synchronization
  1 max_eigenvalue      — dominant common factor
  2 strong_edge_density — prevalence of extreme bilateral links
  3 eigenvalue_entropy  — dispersion (LOW = fragile)
CFI = w1 · z(metrics), oriented so higher = more synchronized = more fragile.
"""
import numpy as np

from engine.cfi.correlation import (
    shrinkage_correlation, average_strength, max_eigenvalue,
    strong_edge_density, eigenvalue_entropy,
)
from engine.cfi.clean import clean_returns

_EPS = 1e-12
METRIC_NAMES = ("avg_strength", "max_eigenvalue", "strong_edge_density", "eigenvalue_entropy")


def four_metrics(returns_window, *, clean=True):
    """Return the 4-metric vector for a (N,T) returns window, or None if degenerate."""
    R = np.asarray(returns_window, dtype=float)
    if R.ndim != 2:
        return None
    n, t = R.shape
    if n < 2 or t < 2:
        return None
    if clean:
        R = clean_returns(R)
    mask = R.std(axis=1) > _EPS
    R = R[mask]
    if R.shape[0] < 2:
        return None
    try:
        C = shrinkage_correlation(R)
    except Exception:
        return None
    return np.array([
        average_strength(C),
        max_eigenvalue(C, normalize=True),
        strong_edge_density(C, rho=0.3),
        eigenvalue_entropy(C),
    ])


def rolling_metrics(returns, *, fit_window=40, clean=True):
    """List of 4-metric vectors over rolling windows (skips degenerate windows)."""
    R = np.asarray(returns, dtype=float)
    if R.ndim != 2:
        return []
    _, T = R.shape
    out = []
    for t in range(0, T - fit_window + 1):
        m = four_metrics(R[:, t:t + fit_window], clean=clean)
        out.append(m if m is not None else None)
    return out


class CFIModel:
    """Standardize the 4 metrics and project onto PC1 (fitted on a reference set)."""

    def __init__(self):
        self.mean = None
        self.std = None
        self.w1 = None

    def fit(self, metric_rows):
        X = np.asarray([m for m in metric_rows if m is not None], dtype=float)
        if X.shape[0] < 4:
            raise ValueError("need >= 4 metric windows to fit PCA")
        self.mean = X.mean(axis=0)
        self.std = X.std(axis=0) + _EPS
        Xs = (X - self.mean) / self.std
        cov = np.cov(Xs, rowvar=False)
        vals, vecs = np.linalg.eigh(cov)
        w1 = vecs[:, -1]                       # eigenvector of largest eigenvalue
        if w1[0] < 0:                          # orient: avg_strength loads positive
            w1 = -w1
        self.w1 = w1
        return self

    def score(self, metrics):
        """CFI value(s) for a 4-vector or an (M,4) array; NaN for None rows."""
        if metrics is None:
            return float("nan")
        m = np.asarray(metrics, dtype=float)
        z = (m - self.mean) / self.std
        return float(z @ self.w1) if m.ndim == 1 else z @ self.w1

    def rolling_cfi(self, returns, *, fit_window=40, clean=True):
        """CFI time series over rolling windows (NaN where degenerate)."""
        return [self.score(m) if m is not None else float("nan")
                for m in rolling_metrics(returns, fit_window=fit_window, clean=clean)]
