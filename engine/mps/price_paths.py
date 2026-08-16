"""Tensor-network price-path sampler — forecast fan chart (arXiv:2402.17148 direction).

The paper generates asset PRICE PATHS with an MPS/tensor-network generative model. Here
a tractable version: model ETH log-return dynamics as an order-k tensor-train transition
(captures volatility clustering), fit on historical returns, then SAMPLE many forward
return paths → cumulate to price paths → percentile bands (fan chart) + P(drawdown).

Deterministic fit (counts), stochastic forward sampling. Returns are scale-free so a model
fit on one period transfers to another period's current price. Indicative on small data.
"""
import numpy as np


class PricePathSampler:
    def __init__(self, n_bins=9, order=2, laplace=1.0):
        self.n_bins = n_bins
        self.order = order
        self.laplace = laplace
        self.edges = None
        self.centers = None       # representative log-return per bin
        self.T = None             # P(next_bin | last `order` bins)

    def _bin(self, returns):
        return np.clip(np.digitize(np.asarray(returns, dtype=float), self.edges), 0, self.n_bins - 1)

    def fit(self, return_series_list):
        allr = np.concatenate([np.asarray(s, dtype=float) for s in return_series_list if len(s)])
        allr = allr[np.isfinite(allr)]
        qs = np.linspace(0, 1, self.n_bins + 1)
        self.edges = np.unique(np.quantile(allr, qs))[1:-1]  # inner edges
        if len(self.edges) < 1:
            self.edges = np.array([0.0])
        self.n_bins = len(self.edges) + 1
        b = self._bin(allr)
        # representative return per bin = mean of training returns in that bin
        self.centers = np.zeros(self.n_bins)
        for k in range(self.n_bins):
            m = allr[b == k]
            self.centers[k] = m.mean() if len(m) else 0.0
        # order-k transition tensor
        shape = (self.n_bins,) * (self.order + 1)
        counts = np.full(shape, self.laplace, dtype=float)
        for series in return_series_list:
            r = np.asarray(series, dtype=float)
            r = r[np.isfinite(r)]
            bb = self._bin(r)
            for i in range(len(bb) - self.order):
                counts[tuple(bb[i:i + self.order + 1])] += 1.0
        self.T = counts / counts.sum(axis=-1, keepdims=True)
        return self

    def forecast(self, recent_returns, current_price, *, horizon=48, n_paths=500,
                 drawdown=0.10, seed=0):
        """Sample forward price paths → percentile bands + P(drawdown) within horizon."""
        rng = np.random.default_rng(seed)
        ctx0 = list(self._bin(recent_returns))[-self.order:]
        while len(ctx0) < self.order:
            ctx0 = [self.n_bins // 2] + ctx0
        prices = np.empty((n_paths, horizon))
        for p in range(n_paths):
            ctx, price = list(ctx0), float(current_price)
            for h in range(horizon):
                nb = int(rng.choice(self.n_bins, p=self.T[tuple(ctx)]))
                price *= float(np.exp(self.centers[nb]))
                prices[p, h] = price
                ctx = ctx[1:] + [nb]
        pct = {q: np.percentile(prices, q, axis=0) for q in (10, 25, 50, 75, 90)}
        min_ret = prices.min(axis=1) / current_price - 1.0
        return {
            "current_price": round(float(current_price), 2),
            "horizon": horizon,
            "bands": [
                {"step": h + 1,
                 "p10": round(float(pct[10][h]), 2), "p25": round(float(pct[25][h]), 2),
                 "p50": round(float(pct[50][h]), 2), "p75": round(float(pct[75][h]), 2),
                 "p90": round(float(pct[90][h]), 2)}
                for h in range(horizon)
            ],
            "p_drawdown": round(100.0 * float((min_ret <= -drawdown).mean()), 1),
            "drawdown_pct": round(100.0 * drawdown, 0),
            "p_down": round(100.0 * float((prices[:, -1] < current_price).mean()), 1),
        }
