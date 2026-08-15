"""MPS (tensor-train) generative density model — behavioral anomaly filter.

Inspired by arXiv:2402.17148 (MPS as a generative model for financial time series).
We learn the joint distribution of "normal" DeFi behaviour over a small feature vector
(the 4 CFI correlation metrics), represented as a Matrix Product State via TT-SVD of the
empirical density tensor. A window with LOW likelihood under the normal model is
out-of-distribution → an anomaly. Used as a PRECISION FILTER: confirm an alert only when
the window is both fragile (entropy RED) and anomalous (low MPS likelihood).

Deterministic (SVD-based, no unstable gradient training). The bond dimension is the
"quantum-inspired" knob: full rank = exact empirical density, low rank = compressed.
Requires abundant clean-normal training windows to be meaningful.
"""
import numpy as np

_EPS = 1e-12


def tt_svd(tensor, bond_dim):
    """Decompose a d-dim tensor into an MPS/tensor-train (cores), truncated to bond_dim."""
    shape = tensor.shape
    d = len(shape)
    cores, r = [], 1
    M = tensor.reshape(shape[0], -1)
    for i in range(d - 1):
        M = M.reshape(r * shape[i], -1)
        U, S, Vt = np.linalg.svd(M, full_matrices=False)
        rnew = min(bond_dim, len(S))
        U, S, Vt = U[:, :rnew], S[:rnew], Vt[:rnew, :]
        cores.append(U.reshape(r, shape[i], rnew))
        M = np.diag(S) @ Vt
        r = rnew
    cores.append(M.reshape(r, shape[d - 1], 1))
    return cores


class MPSBornDensity:
    """MPS density over discretized features. fit() learns normal; log_prob() scores."""

    def __init__(self, n_bins=6, bond_dim=4, laplace=1.0):
        self.n_bins = n_bins
        self.bond_dim = bond_dim
        self.laplace = laplace
        self.edges = None
        self.cores = None

    def _digitize(self, X):
        X = np.atleast_2d(np.asarray(X, dtype=float))
        idx = np.empty(X.shape, dtype=int)
        for j in range(X.shape[1]):
            idx[:, j] = np.clip(np.digitize(X[:, j], self.edges[j][1:-1]), 0, self.n_bins - 1)
        return idx

    def fit(self, X):
        X = np.asarray(X, dtype=float)
        d = X.shape[1]
        # EQUAL-WIDTH edges over the training range: dense centre = high mass, sparse
        # tails = low mass. Out-of-range points clip to the sparse edge bins → flagged
        # as anomalous (quantile bins would equalise mass and hide anomalies).
        self.edges = []
        for j in range(d):
            lo, hi = float(X[:, j].min()), float(X[:, j].max())
            if hi <= lo:
                hi = lo + 1e-9
            self.edges.append(np.linspace(lo, hi, self.n_bins + 1))
        idx = self._digitize(X)
        counts = np.full((self.n_bins,) * d, self.laplace, dtype=float)
        for row in idx:
            counts[tuple(row)] += 1.0
        density = counts / counts.sum()
        self.cores = tt_svd(density, self.bond_dim)
        return self

    def log_prob(self, x):
        """log P(x) under the MPS normal model (single feature vector)."""
        idx = self._digitize(np.asarray(x, dtype=float).reshape(1, -1))[0]
        v = self.cores[0][0, idx[0], :]
        for i in range(1, len(self.cores)):
            v = v @ self.cores[i][:, idx[i], :]
        p = float(v.reshape(()))
        return float(np.log(max(p, _EPS)))

    def anomaly(self, x):
        """Higher = more out-of-distribution (−log P)."""
        return -self.log_prob(x)
