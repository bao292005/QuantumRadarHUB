"""Return-matrix cleaning — MAD anomaly clipping + winsorization.

Adapted from arXiv:2601.08540 §II.B–C (systemic-risk CFI paper), which flags technical
anomalies via median-absolute-deviation and winsorizes returns before correlation, so
oracle glitches / thin-pool spikes do not create spurious synchronization (a major
source of false alarms). Applied per contract row on the (N × T) log-returns matrix.
"""
import numpy as np

_EPS = 1e-12
_MAD_SCALE = 1.4826  # MAD → std for normal data


def winsorize(returns, pct=0.005):
    """Clip each row's returns to its [pct, 1-pct] quantiles."""
    R = np.asarray(returns, dtype=float).copy()
    if R.ndim != 2 or R.shape[1] < 3:
        return R
    lo = np.quantile(R, pct, axis=1, keepdims=True)
    hi = np.quantile(R, 1 - pct, axis=1, keepdims=True)
    return np.clip(R, lo, hi)


def mad_clip(returns, k=12.0):
    """Clip values beyond k robust-sigmas (median ± k·1.4826·MAD) per row."""
    R = np.asarray(returns, dtype=float).copy()
    if R.ndim != 2 or R.shape[1] < 3:
        return R
    med = np.median(R, axis=1, keepdims=True)
    mad = np.median(np.abs(R - med), axis=1, keepdims=True) + _EPS
    band = k * _MAD_SCALE * mad
    return np.clip(R, med - band, med + band)


def clean_returns(returns, *, winsor_pct=0.005, mad_k=12.0):
    """Winsorize then MAD-clip the returns matrix (rows = contracts)."""
    return mad_clip(winsorize(returns, winsor_pct), mad_k)
