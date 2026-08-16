"""FastAPI service (Story 3.3, FR16).

Endpoints:
  POST /subscribe   {"url": ...}   register a webhook
  POST /unsubscribe {"url": ...}   remove a webhook
  GET  /score                      current fragility score + level
  GET  /history?n=                 rolling score timeline
  POST /ingest      <tick event>   feed one on-chain event → score → (maybe) alert

The alert emit callback fans out to subscribers; every ingest records a timeline point.
"""
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.scoring import alert_level
from engine.mps.scenario import MPSScenario


@lru_cache(maxsize=1)
def _fit_scenario_model():
    """Fit the MPS-generative scenario model on a score trajectory (cont_q2_2022 proxy)."""
    try:
        from ingestion.csv_loader import load_events
        from engine.mps.v2 import rolling_scores
        from engine.scoring import score_100, FIT_WINDOW
        from tools._common import fixture_returns
        p = Path("fixtures/backtest/cont_q2_2022.csv.gz")
        if not p.exists():
            return None
        _, R = fixture_returns(load_events(str(p)))
        if R is None or R.shape[1] < FIT_WINDOW:
            return None
        series = [score_100(x) for x in rolling_scores(R, fit_window=FIT_WINDOW)]
        return MPSScenario(order=2).fit([series])
    except Exception:
        return None
from emitter.orchestrator import RealtimeAlerter
from emitter.extension_state import ExtensionState, build_extension_snapshot
from emitter.registry import SubscriberRegistry
from emitter.replay import ReplayDriver
from emitter.score_store import ScoreStore
from emitter.webhook import fan_out_sync


class Subscription(BaseModel):
    url: str


class ProtectionModeUpdate(BaseModel):
    mode: Literal["off", "advisor", "auto"]


class PolicyUpdate(BaseModel):
    enabled: bool


class ReplayRequest(BaseModel):
    fixture: str
    speed: float = 1.0


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
    replay = ReplayDriver(alerter, store)
    scenario_model = _fit_scenario_model()

    app.state.registry = registry
    app.state.store = store
    app.state.alerter = alerter
    app.state.extension_state = extension_state
    app.state.replay = replay

    # Warm the timeline cache in the background so the FIRST time a crisis is opened
    # it renders instantly (build_timeline is ~5s cold, ~0s cached). Skipped under
    # pytest to avoid loading heavy fixtures during tests.
    if "PYTEST_CURRENT_TEST" not in os.environ and not os.environ.get("QUANTUMRADAR_NO_WARM"):
        def _warm():
            try:
                from demo.dashboard import build_timeline, _available_fixtures
                names = [f["name"] for f in _available_fixtures()]
                ordered = ["luna_2022_05_09"] + [n for n in names if n != "luna_2022_05_09"]
                for n in ordered:
                    build_timeline(n)
            except Exception:
                pass
        threading.Thread(target=_warm, daemon=True).start()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "quantumradar-api", "version": "1"}

    @app.get("/api/v1/extension/snapshot")
    def extension_snapshot():
        snap = build_extension_snapshot(alerter, store, extension_state)
        # Real scenario probabilities from the MPS-generative model (replace demo when live)
        if snap["source"] == "live" and scenario_model is not None:
            scores = [h["score"] for h in store.history(8)]
            if len(scores) >= 2:
                probs = scenario_model.scenarios(scores[-scenario_model.order:], horizon=36, n_paths=400)
                for sc in snap.get("scenarios", []):
                    if sc.get("id") in probs:
                        sc["probability"] = probs[sc["id"]]
        return snap

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

    @app.post("/api/v1/replay")
    def start_replay(req: ReplayRequest):
        result = replay.start(req.fixture, req.speed)
        if not result.get("ok"):
            raise HTTPException(status_code=404, detail=result.get("error", "fixture not available"))
        return result

    @app.get("/api/v1/replay")
    def replay_status():
        return replay.status()

    @app.post("/api/v1/replay/stop")
    def stop_replay():
        return replay.stop()

    @app.get("/api/v1/backtest/fixtures")
    def backtest_fixtures():
        from demo.dashboard import _available_fixtures
        return {"fixtures": _available_fixtures()}

    @app.get("/api/v1/backtest/timeline")
    def backtest_timeline(fixture: str = "luna_2022_05_09"):
        from demo.dashboard import build_timeline
        return build_timeline(fixture)

    @app.get("/api/v1/backtest/forecast")
    def backtest_forecast(fixture: str = "luna_2022_05_09", i: int = 0):
        from demo.dashboard import forecast_at
        return forecast_at(fixture, i)

    @app.get("/api/v1/backtest/corr")
    def backtest_corr(fixture: str = "luna_2022_05_09", i: int = 0):
        from demo.dashboard import corr_at
        return corr_at(fixture, i)

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
