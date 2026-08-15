"""Story 3.4 tests — dashboard timeline + endpoints (needs luna fixture)."""
from pathlib import Path

import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from demo.dashboard import build_timeline, create_app

_HAS_LUNA = (Path("fixtures/backtest/luna_2022_05_09.csv.gz")).exists()
pytestmark = pytest.mark.skipif(not _HAS_LUNA, reason="luna fixture not extracted")


def test_timeline_structure():
    t = build_timeline("luna_2022_05_09")
    assert "points" in t and len(t["points"]) > 10
    assert t["cascade_block"] == 14_732_113
    p = t["points"][0]
    assert set(p) == {"block", "score", "level", "rcs"}


def test_red_appears_before_cascade():
    t = build_timeline("luna_2022_05_09")
    cascade = t["cascade_block"]
    reds_pre = [p for p in t["points"] if p["level"] == "RED" and p["block"] <= cascade]
    assert reds_pre, "expected at least one RED alert before the cascade block"


def test_endpoints():
    c = TestClient(create_app("luna_2022_05_09"))
    assert c.get("/").status_code == 200
    body = c.get("/api/timeline").json()
    assert body["fixture"] == "luna_2022_05_09" and body["points"]
