"""Persistent state and response assembly for the browser extension API."""

import json
import os
import threading
import time
from pathlib import Path

from engine.scoring import alert_level


POLICY_DEFINITIONS = [
    {
        "id": 1,
        "condition": "Liquidity Crisis > 80%",
        "actions": ["Bán 30% AAVE", "Chuyển sang USDC"],
        "goal": "Giảm rủi ro danh mục",
    },
    {
        "id": 2,
        "condition": "Stablecoin Depeg xác nhận",
        "actions": ["Thoát toàn bộ Stablecoin rủi ro"],
        "goal": "Bảo vệ tài sản ổn định",
    },
    {
        "id": 3,
        "condition": "Contagion Risk > 90%",
        "actions": ["Emergency Exit", "Về trạng thái phòng thủ"],
        "goal": "Bảo toàn toàn bộ vốn",
    },
]

DEMO_ACTIONS = [
    {"time": "14:32", "label": "AI phát hiện Liquidity Shock", "tone": "yellow"},
    {"time": "14:35", "label": "AI kích hoạt Policy #01", "tone": "orange"},
    {"time": "14:36", "label": "Bán 30% AAVE thành công", "tone": "cyan"},
    {"time": "14:37", "label": "Chuyển sang USDC hoàn tất", "tone": "cyan"},
    {"time": "14:40", "label": "Danh mục giảm rủi ro 18%", "tone": "green"},
]


class ExtensionState:
    """Stores user-controlled protection settings outside the algorithm state."""

    VALID_MODES = {"off", "advisor", "auto"}

    def __init__(self, path=None):
        default_path = Path(os.getenv("QUANTUMRADAR_STATE_DIR", ".quantumradar")) / "protection.json"
        self.path = Path(path) if path is not None else default_path
        self._lock = threading.RLock()
        self._mode = "auto"
        self._enabled = {policy["id"]: True for policy in POLICY_DEFINITIONS}
        self._load()

    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("mode") in self.VALID_MODES:
                self._mode = data["mode"]
            enabled = data.get("enabled", {})
            for policy_id in self._enabled:
                value = enabled.get(str(policy_id), enabled.get(policy_id))
                if isinstance(value, bool):
                    self._enabled[policy_id] = value
        except (OSError, json.JSONDecodeError, AttributeError):
            return

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"mode": self._mode, "enabled": self._enabled}
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def set_mode(self, mode):
        if mode not in self.VALID_MODES:
            raise ValueError(f"unsupported mode: {mode}")
        with self._lock:
            self._mode = mode
            self._save()
            return self.snapshot()

    def set_policy(self, policy_id, enabled):
        if policy_id not in self._enabled:
            raise KeyError(policy_id)
        with self._lock:
            self._enabled[policy_id] = bool(enabled)
            self._save()
            return self.snapshot()

    def snapshot(self):
        with self._lock:
            policies = [
                {**definition, "enabled": self._enabled[definition["id"]]}
                for definition in POLICY_DEFINITIONS
            ]
            active_count = sum(policy["enabled"] for policy in policies)
            return {
                "mode": self._mode,
                "policies": policies,
                "active_count": active_count,
                "ready": self._mode != "off" and active_count > 0,
            }


def build_extension_snapshot(alerter, store, extension_state):
    """Create the stable UI contract, using demo values until live ingest is warm."""
    latest = store.latest()
    is_live = latest is not None
    score = round(float(alerter.current_score), 2) if is_live else 78.0
    level = alert_level(score)
    rcs = [
        {"contract": str(contract), "contribution": round(float(value), 4)}
        for contract, value in list(alerter.current_rcs.items())[:5]
    ]
    if is_live:
        timeline = []
        for point in store.history(5):
            point_score = float(point["score"])
            tone = "red" if point_score >= 90 else ("yellow" if point_score >= 70 else "cyan")
            timeline.append({
                "time": time.strftime("%H:%M", time.localtime(point["timestamp"])),
                "label": f"Risk Score cập nhật: {point_score:.1f}/100",
                "tone": tone,
            })
    else:
        timeline = DEMO_ACTIONS

    probability = min(95, max(35, round(score * 0.92)))

    # Live: derive the primary risk + risk list from the REAL RCS epicenter.
    # Demo / no-RCS: keep the illustrative defaults. (scenarios & portfolio below
    # remain illustrative — there is no live portfolio feed.)
    if is_live and rcs:
        severity = "high" if score >= 90 else ("medium" if score >= 70 else "low")
        status_text = "Rủi ro cao" if score >= 90 else ("Trung bình" if score >= 70 else "Theo dõi")
        primary_risk = f"{rcs[0]['contract']} (RCS epicenter)"
        risks = []
        for rank, item in enumerate(rcs[:3]):
            risks.append({
                "id": str(item["contract"]),
                "title": f"{item['contract']} — RCS epicenter",
                "probability": min(95, max(35, round(score * (0.95 - 0.2 * rank)))),
                "horizon": "12-24h",
                "status": status_text if rank == 0 else "Theo dõi",
                "severity": severity if rank == 0 else ("medium" if rank == 1 else "low"),
            })
    else:
        primary_risk = "Liquidity Shock"
        risks = [
            {"id": "liquidity", "title": "Liquidity Shock", "probability": probability, "horizon": "12-24h", "status": "Rủi ro cao", "severity": "high"},
            {"id": "depeg", "title": "Stablecoin Depeg", "probability": 58, "horizon": "24-48h", "status": "Trung bình", "severity": "medium"},
            {"id": "cascade", "title": "Lending Cascade", "probability": 45, "horizon": "2-3 ngày", "status": "Theo dõi", "severity": "low"},
        ]

    return {
        "version": "1",
        "generated_at": time.time(),
        "source": "live" if is_live else "demo",
        "market": {
            "symbol": "AAVEUSDT",
            "stress_score": score,
            "warning_score": min(100, round(score + 6, 2)),
            "alert_level": level or "CALM",
            "probability": probability,
            "confidence": 89,
            "horizon": "12-24h",
            "primary_risk": primary_risk,
            "rcs": rcs,
        },
        "risks": risks,
        "scenarios": [
            {"id": "liquidity", "title": "Liquidity Shock", "probability": 50, "impact": "-21%", "timeframe": "24-48h", "level": "Nghiêm trọng"},
            {"id": "recovery", "title": "Recovery", "probability": 35, "impact": "+6%", "timeframe": "72h", "level": "Tích cực"},
            {"id": "contagion", "title": "Contagion Event", "probability": 15, "impact": "-38%", "timeframe": "6-12h", "level": "Rất nghiêm trọng"},
        ],
        "portfolio": {
            "expected_loss": "-8%",
            "risk_score": score,
            "safe_allocation": 17,
            "assets": [
                {"symbol": "AAVE", "allocation": 35, "risk": "Cao", "loss": "-8.0%"},
                {"symbol": "ETH", "allocation": 28, "risk": "Trung", "loss": "-3.1%"},
                {"symbol": "BNB", "allocation": 20, "risk": "Thấp", "loss": "-1.2%"},
                {"symbol": "USDC", "allocation": 17, "risk": "An toàn", "loss": "0%"},
            ],
        },
        "protection": extension_state.snapshot(),
        "actions": timeline,
    }
