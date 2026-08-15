"""MPS-Born density model — mechanism sanity (in-distribution > out-of-distribution)."""
import numpy as np

from engine.mps.generative import MPSBornDensity, tt_svd


def test_tt_svd_reconstructs_small_tensor():
    rng = np.random.default_rng(0)
    T = rng.random((5, 5, 5, 5)); T /= T.sum()
    cores = tt_svd(T, bond_dim=25)  # full rank (middle bond needs 25) → near-exact
    # contract a few random cells and compare
    for _ in range(20):
        idx = tuple(rng.integers(0, 5, size=4))
        v = cores[0][0, idx[0], :]
        for i in range(1, 4):
            v = v @ cores[i][:, idx[i], :]
        assert abs(float(v.reshape(())) - T[idx]) < 1e-6


def test_in_distribution_has_higher_likelihood():
    rng = np.random.default_rng(42)
    normal = rng.normal(0, 1, size=(4000, 4))  # learn N(0,1)^4 as "normal"
    m = MPSBornDensity(n_bins=6, bond_dim=4).fit(normal)
    lp_in = m.log_prob([0, 0, 0, 0])          # near the mode
    lp_out = m.log_prob([6, 6, 6, 6])         # far out-of-distribution
    assert lp_in > lp_out
    assert m.anomaly([6, 6, 6, 6]) > m.anomaly([0, 0, 0, 0])


def test_log_prob_finite():
    rng = np.random.default_rng(1)
    m = MPSBornDensity().fit(rng.normal(0, 1, size=(500, 4)))
    assert np.isfinite(m.log_prob([100, -100, 0, 0]))  # extreme point stays finite
