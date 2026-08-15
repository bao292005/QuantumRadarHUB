"""Story 3.3 tests — FastAPI endpoints (mock scorer, isolated registry/store)."""
import pytest

pytest.importorskip("httpx")  # TestClient needs httpx
from fastapi.testclient import TestClient

from emitter.api import create_app
from emitter.extension_state import ExtensionState
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
        extension_state=ExtensionState(tmp_path / "protection.json"),
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


def test_extension_snapshot_uses_demo_until_first_ingest(tmp_path):
    c = _client(tmp_path, {100: 84})
    snapshot = c.get("/api/v1/extension/snapshot").json()
    assert snapshot["source"] == "demo"
    assert snapshot["market"]["stress_score"] == 78
    assert snapshot["protection"]["active_count"] == 3

    c.post("/ingest", json={"block_number": 100})
    snapshot = c.get("/api/v1/extension/snapshot").json()
    assert snapshot["source"] == "live"
    assert snapshot["market"]["stress_score"] == 84


def test_protection_mode_and_policy_are_persisted(tmp_path):
    c = _client(tmp_path, {})
    assert c.put("/api/v1/protection/mode", json={"mode": "advisor"}).json()["mode"] == "advisor"
    policy = c.patch("/api/v1/protection/policies/1", json={"enabled": False}).json()
    assert policy["active_count"] == 2

    persisted = ExtensionState(tmp_path / "protection.json").snapshot()
    assert persisted["mode"] == "advisor"
    assert persisted["policies"][0]["enabled"] is False


def test_protection_rejects_invalid_updates(tmp_path):
    c = _client(tmp_path, {})
    assert c.put("/api/v1/protection/mode", json={"mode": "invalid"}).status_code == 422
    assert c.patch("/api/v1/protection/policies/99", json={"enabled": True}).status_code == 404


def test_extension_cors_allows_chrome_origin(tmp_path):
    c = _client(tmp_path, {})
    response = c.options(
        "/api/v1/extension/snapshot",
        headers={
            "Origin": "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"].startswith("chrome-extension://")
