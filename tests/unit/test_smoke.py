"""Epic 1 smoke tests (NFR7 gate): synchronized > uncorrelated.

Fail here = wrong entropy formula. Run: python3 -m pytest tests/unit/test_smoke.py
"""
import numpy as np
from engine.mps.v2 import mps_correlation_score, rcs_scores, rolling_scores
from engine.cfi.correlation import eigenvalue_entropy, shrinkage_correlation
from engine.scoring import score_100, alert_level, SCORE_FLOOR, SCORE_CEIL


def _sync_uncorr(seed=42, n=8, t=60):
    rng = np.random.default_rng(seed)
    factor = rng.standard_normal(t)
    sync = np.array([factor + 0.05 * rng.standard_normal(t) for _ in range(n)])
    uncorr = rng.standard_normal((n, t))
    return sync, uncorr


def test_synchronized_beats_uncorrelated():
    sync, uncorr = _sync_uncorr()
    assert mps_correlation_score(sync) > mps_correlation_score(uncorr)


def test_eigenvalue_entropy_in_unit_range():
    sync, _ = _sync_uncorr()
    h = eigenvalue_entropy(shrinkage_correlation(sync))
    assert 0.0 <= h <= 1.0


def test_score_100_endpoints():
    assert score_100(SCORE_FLOOR) == 0.0
    assert score_100(SCORE_CEIL) == 100.0
    assert score_100(-1.0) == 0.0 and score_100(1.0) == 100.0


def test_alert_level_thresholds():
    assert alert_level(95) == "RED"
    assert alert_level(75) == "YELLOW"
    assert alert_level(50) is None


def test_rcs_returns_sorted_desc():
    sync, _ = _sync_uncorr()
    rcs = rcs_scores(sync, [f"c{i}" for i in range(sync.shape[0])])
    vals = list(rcs.values())
    assert vals == sorted(vals, reverse=True)


def test_rolling_scores_length():
    sync, _ = _sync_uncorr(t=60)
    scores = rolling_scores(sync, fit_window=40)
    assert len(scores) == 60 - 40 + 1


def test_degenerate_inputs_safe():
    assert mps_correlation_score(np.zeros((1, 5))) == 0.0
    assert mps_correlation_score(np.ones((5, 1))) == 0.0
