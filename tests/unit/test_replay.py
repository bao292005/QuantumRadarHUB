"""Replay driver + live snapshot integration (needs luna fixture)."""
import time
from pathlib import Path

import pytest

_HAS_LUNA = Path("fixtures/backtest/luna_2022_05_09.csv.gz").exists()
pytestmark = pytest.mark.skipif(not _HAS_LUNA, reason="luna fixture not extracted")

from emitter.replay import build_replay_points, ReplayDriver
from emitter.orchestrator import RealtimeAlerter
from emitter.score_store import ScoreStore
from emitter.extension_state import ExtensionState, build_extension_snapshot


def test_build_points_hits_red():
    pts = build_replay_points("luna_2022_05_09")
    assert pts and set(pts[0]) == {"block", "score", "rcs"}
    assert any(p["score"] >= 90 for p in pts)  # LUNA reaches RED


def test_missing_fixture():
    r = ReplayDriver(RealtimeAlerter(), ScoreStore()).start("nope", speed=1)
    assert r["ok"] is False


def test_driver_drives_alerter_and_store():
    a, s = RealtimeAlerter(), ScoreStore()
    d = ReplayDriver(a, s)
    d.start("luna_2022_05_09", speed=60)
    time.sleep(1.2)
    d.stop()
    assert len(s) > 0 and a.current_score > 0
    assert d.status()["n"] > 0


def test_live_snapshot_derives_risks_from_rcs():
    a, s = RealtimeAlerter(), ScoreStore()
    a.current_score = 95.0
    a.current_rcs = {"cUSDC": 0.02, "WBTC/USDC": 0.01, "DAI/WETH": 0.005}
    s.append(95.0, block_number=1, alert_level="RED", rcs=[{"contract": "cUSDC", "contribution": 0.02}])
    snap = build_extension_snapshot(a, s, ExtensionState(Path("/tmp/qr_test_prot.json")))
    assert snap["source"] == "live"
    assert snap["market"]["primary_risk"].startswith("cUSDC")
    assert snap["risks"][0]["id"] == "cUSDC"
    assert snap["risks"][0]["severity"] == "high"
