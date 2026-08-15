"""FastAPI service (Story 3.3, FR16).

Endpoints:
  POST /subscribe   {"url": ...}   register a webhook
  POST /unsubscribe {"url": ...}   remove a webhook
  GET  /score                      current fragility score + level
  GET  /history?n=                 rolling score timeline
  POST /ingest      <tick event>   feed one on-chain event → score → (maybe) alert

The alert emit callback fans out to subscribers; every ingest records a timeline point.
"""
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.scoring import alert_level
from emitter.orchestrator import RealtimeAlerter
from emitter.extension_state import ExtensionState, build_extension_snapshot
from emitter.registry import SubscriberRegistry
from emitter.score_store import ScoreStore
from emitter.webhook import fan_out_sync


class Subscription(BaseModel):
    url: str


class ProtectionModeUpdate(BaseModel):
    mode: Literal["off", "advisor", "auto"]


class PolicyUpdate(BaseModel):
    enabled: bool


def create_app(*, registry=None, store=None, alerter=None, scorer=None, extension_state=None):
    app = FastAPI(title="QuantumRadar", version="1")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=(
            r"^(chrome-extension://[a-p]{32}"
            r"|http://localhost(?::\d+)?"
            r"|http://127\.0\.0\.1(?::\d+)?)$"
        ),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    registry = registry or SubscriberRegistry()
    store = store or ScoreStore()
    extension_state = extension_state or ExtensionState()

    def _emit(alert):
        urls = registry.list()
        if urls:
            try:
                fan_out_sync(urls, alert)
            except Exception:
                pass

    alerter = alerter or RealtimeAlerter(emit=_emit, scorer=scorer)

    app.state.registry = registry
    app.state.store = store
    app.state.alerter = alerter
    app.state.extension_state = extension_state

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "quantumradar-api", "version": "1"}

    @app.get("/api/v1/extension/snapshot")
    def extension_snapshot():
        return build_extension_snapshot(alerter, store, extension_state)

    @app.get("/api/v1/protection")
    def protection():
        return extension_state.snapshot()

    @app.put("/api/v1/protection/mode")
    def update_protection_mode(update: ProtectionModeUpdate):
        return extension_state.set_mode(update.mode)

    @app.patch("/api/v1/protection/policies/{policy_id}")
    def update_policy(policy_id: int, update: PolicyUpdate):
        try:
            return extension_state.set_policy(policy_id, update.enabled)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="policy not found") from exc

    @app.get("/api/v1/actions")
    def actions(n: int = 50):
        if n < 1 or n > 500:
            raise HTTPException(status_code=422, detail="n must be between 1 and 500")
        return {"actions": store.history(n)}

    @app.post("/subscribe")
    def subscribe(sub: Subscription):
        return {"url": sub.url, "new": registry.add(sub.url)}

    @app.post("/unsubscribe")
    def unsubscribe(sub: Subscription):
        return {"url": sub.url, "removed": registry.remove(sub.url)}

    @app.get("/score")
    def score():
        return {
            "score": alerter.current_score,
            "alert_level": alert_level(alerter.current_score),
            "rcs": [{"contract": str(c), "contribution": float(v)}
                    for c, v in list(alerter.current_rcs.items())[:5]],
        }

    @app.get("/history")
    def history(n: int = 200):
        return {"history": store.history(n)}

    @app.post("/ingest")
    def ingest(event: dict):
        alert = alerter.ingest(event)
        store.append(
            alerter.current_score,
            block_number=event.get("block_number"),
            alert_level=alert_level(alerter.current_score),
            rcs=[{"contract": str(c), "contribution": float(v)}
                 for c, v in list(alerter.current_rcs.items())[:5]],
        )
        return {"score": alerter.current_score, "alerted": alert is not None}

    return app


app = create_app()
