"""MPS-generative scenario forecaster — dynamics sanity."""
import numpy as np

from engine.mps.scenario import MPSScenario


def test_escalating_dynamics_favour_contagion():
    # training: trajectories that, once high, stay high (persistent RED)
    high = [[95, 96, 97, 98, 99, 100, 100, 100]] * 50
    m = MPSScenario(order=2).fit(high + [[10, 12, 11, 9, 8]] * 20)
    s = m.scenarios([98, 99], horizon=20, n_paths=500)
    assert sum(s.values()) == 100
    assert s["contagion"] > s["recovery"]  # from a high context, escalation dominates


def test_calming_dynamics_favour_recovery():
    # training: trajectories that decay from high back to calm
    decay = [[95, 80, 60, 40, 20, 10, 5, 5]] * 60
    m = MPSScenario(order=2).fit(decay)
    s = m.scenarios([95, 80], horizon=20, n_paths=500)
    assert s["recovery"] >= s["contagion"]


def test_probabilities_sum_to_100():
    rng = np.random.default_rng(0)
    series = [rng.integers(0, 100, size=200).tolist() for _ in range(10)]
    m = MPSScenario().fit(series)
    s = m.scenarios([50, 60], horizon=30, n_paths=300)
    assert set(s) == {"liquidity", "recovery", "contagion"}
    assert sum(s.values()) == 100
