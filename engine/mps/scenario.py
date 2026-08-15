"""MPS-generative scenario forecaster (arXiv:2402.17148 direction).

The core "MPS" (mps/v2.py) DETECTS fragility; the generative MPS GENERATES futures.
Here we model the temporal dynamics of the fragility score as an order-k tensor-train
transition (a tensor-network / MPS over recent states), fit on historical score
trajectories, then SAMPLE forward paths to derive real scenario probabilities
(liquidity-shock / recovery / contagion) — replacing hardcoded demo values.

Deterministic fit (counts), stochastic forward sampling. Needs enough trajectory data
to be meaningful (re-fit on the long calm/eventful spans for a trustworthy model).
"""
import numpy as np

# score → bins by alert semantics: <30 calm, 30-50 low, 50-70 elevated, 70-90 yellow, >=90 red
LEVEL_EDGES = (30.0, 50.0, 70.0, 90.0)


class MPSScenario:
    def __init__(self, order=2, laplace=1.0, edges=LEVEL_EDGES):
        self.order = order
        self.laplace = laplace
        self.edges = np.asarray(edges, dtype=float)
        self.n_bins = len(edges) + 1
        self.T = None  # P(next_bin | last `order` bins) transition tensor (tensor-train form)

    def _bin(self, scores):
        return np.digitize(np.asarray(scores, dtype=float), self.edges)

    def fit(self, series_list):
        """series_list: list of score-time-series (each a 1-D array of 0..100 scores)."""
        shape = (self.n_bins,) * (self.order + 1)
        counts = np.full(shape, self.laplace, dtype=float)
        for series in series_list:
            b = self._bin(series)
            for i in range(len(b) - self.order):
                counts[tuple(b[i:i + self.order + 1])] += 1.0
        self.T = counts / counts.sum(axis=-1, keepdims=True)
        return self

    def sample_path(self, context, horizon, rng):
        """Roll forward `horizon` steps from the last `order` observed scores."""
        ctx = list(self._bin(context))[-self.order:]
        while len(ctx) < self.order:
            ctx = [0] + ctx
        path = []
        for _ in range(horizon):
            nb = int(rng.choice(self.n_bins, p=self.T[tuple(ctx)]))
            path.append(nb)
            ctx = ctx[1:] + [nb]
        return path

    def scenarios(self, context, *, horizon=36, n_paths=500, seed=0):
        """Sample forward paths → % of paths ending in each scenario class."""
        rng = np.random.default_rng(seed)
        cnt = {"liquidity": 0, "recovery": 0, "contagion": 0}
        for _ in range(n_paths):
            p = self.sample_path(context, horizon, rng)
            end = p[-1]
            if end <= 1:                       # settled below 50 → recovered
                cnt["recovery"] += 1
            elif end >= self.n_bins - 1:        # ends maxed (>=90) → contagion
                cnt["contagion"] += 1
            else:                               # elevated / partial shock
                cnt["liquidity"] += 1
        return {k: round(100.0 * v / n_paths) for k, v in cnt.items()}
