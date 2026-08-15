"""Persistence + hysteresis on the locked entropy detector — recall/FP tradeoff.

Alert turns ON only after N consecutive RED (>=90) windows (persistence filters single
-window spikes, the main false-alarm source); once ON it stays until score drops below
the clear threshold (hysteresis, 70). No change to the core — pure post-processing of
the entropy score. Sweeps N and prints crisis pre-cascade detection vs false-alarm
episodes on the control fixtures.

    python3 -m tools.entropy_persist_eval
"""
import sys
from pathlib import Path

import numpy as np

from ingestion.csv_loader import load_events
from engine.mps.v2 import rolling_scores
from engine.scoring import SCORE_FLOOR, SCORE_CEIL, FIT_WINDOW
from tools._common import fixture_returns, window_end_blocks, scored_index_to_block
from tools.extract_fixtures import FIXTURES
from tools.honest_detection_count import CATEGORY

FIXTURE_DIR = Path("fixtures/backtest")
FIRE, CLEAR = 90.0, 70.0
NS = [1, 2, 3, 4, 5]
FP_FIXTURES = ["normal_2023_03_15", "busd_freeze_2023_02", "euler_hack_2023_03"]


def _score100(raw):
    span = SCORE_CEIL - SCORE_FLOOR
    return 100.0 * max(0.0, min(1.0, (raw - SCORE_FLOOR) / span))


def alert_states(scores, N, fire=FIRE, clear=CLEAR):
    on, states = False, []
    for i in range(len(scores)):
        if not on:
            if i + 1 >= N and all(s >= fire for s in scores[i - N + 1:i + 1]):
                on = True
        elif scores[i] < clear:
            on = False
        states.append(on)
    return states


def main():
    data = {}
    for name in FIXTURES:
        path = FIXTURE_DIR / f"{name}.csv.gz"
        if not path.exists():
            continue
        events = load_events(str(path))
        contracts, R = fixture_returns(events)
        if R is None or R.shape[1] < FIT_WINDOW:
            continue
        scores = [_score100(x) for x in rolling_scores(R, fit_window=FIT_WINDOW)]
        ends = window_end_blocks(events)
        blocks = [scored_index_to_block(ends, i) for i in range(len(scores))]
        data[name] = (scores, blocks, FIXTURES[name][2], CATEGORY.get(name, "?"))

    crises = [n for n, v in data.items() if v[3] == "crisis"]

    def episodes(states):
        return sum(1 for i in range(len(states)) if states[i] and (i == 0 or not states[i - 1]))

    def evaluate(N):
        hits, fp = 0, {}
        for name, (scores, blocks, cascade, cat) in data.items():
            st = alert_states(scores, N)
            if cat == "crisis":
                pre = any(st[i] and blocks[i] is not None and (cascade is None or blocks[i] <= cascade)
                          for i in range(len(st)))
                hits += pre
            if name in FP_FIXTURES:
                fp[name] = episodes(st)
        return hits, fp

    print(f"Persistence(N consecutive RED) + hysteresis(fire {FIRE:.0f}/clear {CLEAR:.0f}) on entropy")
    print(f"crises available: {len(crises)}/7 | FP shown as #alert episodes (lower=better)\n")
    hdr = f"{'N':>3} {'crisis/7':>9} {'normal':>8} {'busd':>7} {'euler':>7}"
    print(hdr); print("-" * len(hdr))
    for N in NS:
        hits, fp = evaluate(N)
        print(f"{N:>3} {hits:>7}/{len(crises)} "
              f"{fp.get('normal_2023_03_15',0):>8} {fp.get('busd_freeze_2023_02',0):>7} "
              f"{fp.get('euler_hack_2023_03',0):>7}")
    print("\nN=1 → current detector. Pick largest N keeping crisis=7/7 with fewest FP episodes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
