"""Tensor-network price-path sampler — forecast sanity."""
import numpy as np

from engine.mps.price_paths import PricePathSampler


def _returns(seed, drift, n=2000):
    rng = np.random.default_rng(seed)
    return (drift + 0.01 * rng.standard_normal(n)).tolist()


def test_downtrend_gives_high_drawdown_prob():
    m = PricePathSampler(order=2).fit([_returns(0, -0.01)])   # persistent decline
    f = m.forecast(_returns(1, -0.01)[-5:], 2000.0, horizon=48, n_paths=600)
    assert f["p_down"] > 60 and f["p_drawdown"] > 30


def test_flat_market_low_drawdown():
    m = PricePathSampler(order=2).fit([_returns(2, 0.0)])     # flat
    f = m.forecast([0.0, 0.0], 2000.0, horizon=48, n_paths=600)
    assert f["p_drawdown"] < 25


def test_bands_widen_and_shape():
    m = PricePathSampler().fit([_returns(3, 0.0)])
    f = m.forecast([0.0, 0.0], 2000.0, horizon=30, n_paths=400)
    assert len(f["bands"]) == 30
    b = f["bands"]
    # 90th pct >= median >= 10th pct at every step; band widens over horizon
    assert all(x["p90"] >= x["p50"] >= x["p10"] for x in b)
    assert (b[-1]["p90"] - b[-1]["p10"]) >= (b[0]["p90"] - b[0]["p10"])
