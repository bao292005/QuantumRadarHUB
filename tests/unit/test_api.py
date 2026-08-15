"""Story 3.3 tests — FastAPI endpoints (mock scorer, isolated registry/store)."""
import pytest

pytest.importorskip("httpx")  # TestClient needs httpx
from fastapi.testclient import TestClient

from emitter.api import create_app
from emitter.orchestrator import RealtimeAlerter
from emitter.registry import SubscriberRegistry
from emitter.score_store import ScoreStore


def _client(tmp_path, scores):
    def scorer(events):
        return scores.get(events[-1]["block_number"], 0.0), {"0xa": 0.1}
    alerter = RealtimeAlerter(scorer=scorer)
    app = create_app(
        registry=SubscriberRegistry(tmp_path / "subs.json"),
        store=ScoreStore(),
        alerter=alerter,
    )
    return TestClient(app)


def test_subscribe_dedup(tmp_path):
    c = _client(tmp_path, {})
    assert c.post("/subscribe", json={"url": "http://a/h"}).json()["new"] is True
    assert c.post("/subscribe", json={"url": "http://a/h"}).json()["new"] is False


def test_ingest_updates_score_and_history(tmp_path):
    c = _client(tmp_path, {100: 40, 200: 95})
    c.post("/ingest", json={"block_number": 100})
    r = c.post("/ingest", json={"block_number": 200})
    assert r.json()["score"] == 95 and r.json()["alerted"] is True
    assert c.get("/score").json()["alert_level"] == "RED"
    hist = c.get("/history").json()["history"]
    assert len(hist) == 2 and hist[-1]["score"] == 95


def test_unsubscribe(tmp_path):
    c = _client(tmp_path, {})
    c.post("/subscribe", json={"url": "http://a/h"})
    assert c.post("/unsubscribe", json={"url": "http://a/h"}).json()["removed"] is True
