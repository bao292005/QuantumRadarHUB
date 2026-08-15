"""Replay driver — stream a fixture's REAL fragility timeline into the live API.

Precomputes CFI+MPS score + RCS per window (same engine as the 7/7 gate), then a
background thread advances through them on a timer, updating the alerter's current
score/RCS and appending to the score store. The extension's /snapshot then shows a
real crisis unfolding (score climbs to RED before the cascade) — not demo data.

Scores are precomputed only for speed; they are the identical output of the verbatim
engine, so this is a faithful replay, not synthetic data.
"""
import threading
from functools import lru_cache
from pathlib import Path

from ingestion.csv_loader import load_events
from engine.mps.v2 import rolling_scores, rcs_scores
from engine.scoring import score_100, alert_level, FIT_WINDOW
from tools._common import fixture_returns, window_end_blocks, scored_index_to_block
from tools.extract_fixtures import UNI_POOLS, COMPOUND, AAVE_V2, AAVE_V3, SPARK

FIXTURE_DIR = Path("fixtures/backtest")

_LABELS = {a: f"{t0}/{t1}" for a, t0, t1 in UNI_POOLS}
_LABELS.update({a: f"c{u}" for a, u in COMPOUND})
_LABELS.update({AAVE_V2: "AaveV2", AAVE_V3: "AaveV3", SPARK: "Spark"})


def _label(addr):
    return _LABELS.get(addr, addr[:10])


@lru_cache(maxsize=8)
def build_replay_points(fixture):
    """Precompute [{block, score, rcs{label:contrib}}] for a fixture, or None."""
    path = FIXTURE_DIR / f"{fixture}.csv.gz"
    if not path.exists():
        return None
    events = load_events(str(path))
    contracts, R = fixture_returns(events)
    if R is None or R.shape[1] < FIT_WINDOW:
        return None
    ends = window_end_blocks(events)
    pts = []
    for i, raw in enumerate(rolling_scores(R, fit_window=FIT_WINDOW)):
        s = round(score_100(raw), 2)
        rcs = {}
        if s >= 50:
            r = rcs_scores(R[:, i:i + FIT_WINDOW], contracts)
            rcs = {_label(c): round(float(v), 4) for c, v in list(r.items())[:5]}
        pts.append({"block": scored_index_to_block(ends, i), "score": s, "rcs": rcs})
    return pts


class ReplayDriver:
    """Advances a precomputed real timeline into alerter/store on a background timer."""

    BASE_INTERVAL = 0.3  # seconds per tick at speed 1.0

    def __init__(self, alerter, store):
        self.alerter = alerter
        self.store = store
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._fixture = None
        self._i = 0
        self._n = 0
        self._running = False

    def start(self, fixture, speed=1.0):
        pts = build_replay_points(fixture)
        if pts is None:
            return {"ok": False, "error": f"fixture not available: {fixture}"}
        self.stop()
        self._stop = threading.Event()
        with self._lock:
            self._fixture, self._i, self._n, self._running = fixture, 0, len(pts), True
        interval = max(0.02, self.BASE_INTERVAL / max(0.1, float(speed)))
        self._thread = threading.Thread(target=self._run, args=(pts, interval), daemon=True)
        self._thread.start()
        return {"ok": True, **self.status()}

    def _run(self, pts, interval):
        for idx, p in enumerate(pts):
            if self._stop.is_set():
                break
            self.alerter.current_score = p["score"]
            self.alerter.current_rcs = dict(p["rcs"])
            self.store.append(
                p["score"], block_number=p["block"], alert_level=alert_level(p["score"]),
                rcs=[{"contract": c, "contribution": v} for c, v in p["rcs"].items()],
            )
            with self._lock:
                self._i = idx + 1
            self._stop.wait(interval)
        with self._lock:
            self._running = False

    def stop(self):
        self._stop.set()
        t = self._thread
        if t and t.is_alive():
            t.join(timeout=1.0)
        with self._lock:
            self._running = False
        return self.status()

    def status(self):
        with self._lock:
            return {"running": self._running, "fixture": self._fixture, "i": self._i, "n": self._n}
