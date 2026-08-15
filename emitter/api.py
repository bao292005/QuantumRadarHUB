"""FastAPI service (Story 3.3, FR16).

Endpoints:
  POST /subscribe   {"url": ...}   register a webhook
  POST /unsubscribe {"url": ...}   remove a webhook
  GET  /score                      current fragility score + level
  GET  /history?n=                 rolling score timeline
  POST /ingest      <tick event>   feed one on-chain event → score → (maybe) alert

The alert emit callback fans out to subscribers; every ingest records a timeline point.
"""
from fastapi import FastAPI
from pydantic import BaseModel

from engine.scoring import alert_level
from emitter.orchestrator import RealtimeAlerter
from emitter.registry import SubscriberRegistry
from emitter.score_store import ScoreStore
from emitter.webhook import fan_out_sync


class Subscription(BaseModel):
    url: str


def create_app(*, registry=None, store=None, alerter=None, scorer=None):
    app = FastAPI(title="QuantumRadar", version="1")
    registry = registry or SubscriberRegistry()
    store = store or ScoreStore()

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
