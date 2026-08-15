"""Story 3.1 tests — payload + orchestrator debounce/emit (mock scorer)."""
import json
from pathlib import Path

import jsonschema
import pytest

from emitter.payload import format_alert
from emitter.orchestrator import RealtimeAlerter

_SCHEMA = json.loads(
    (Path(__file__).parents[2] / "contracts" / "fragility_alert.schema.json").read_text()
)


# ---- payload ----
def test_format_alert_below_yellow_is_none():
    assert format_alert(50, {}, 100) is None


def test_format_alert_levels_and_schema():
    a = format_alert(95, {"0xabc": 0.2, "0xdef": 0.1}, 14_732_000)
    assert a["alert_level"] == "RED" and a["score"] == 95.0
    jsonschema.validate(a, _SCHEMA)
    y = format_alert(75, {}, 1)
    assert y["alert_level"] == "YELLOW"
    jsonschema.validate(y, _SCHEMA)


def test_format_alert_top_n():
    rcs = {f"0x{i}": 1.0 / (i + 1) for i in range(10)}
    a = format_alert(91, rcs, 1, top_n=3)
    assert len(a["rcs"]) == 3


# ---- orchestrator debounce ----
def _make_scorer(score_by_block):
    def scorer(events):
        b = events[-1]["block_number"]
        return score_by_block.get(b, 0.0), {"0xa": 0.1, "0xb": 0.05}
    return scorer


def test_no_emit_below_yellow():
    fired = []
    a = RealtimeAlerter(emit=fired.append, scorer=_make_scorer({100: 50, 200: 69}))
    a.ingest({"block_number": 100})
    a.ingest({"block_number": 200})
    assert fired == []


def test_emit_on_rising_level_and_debounce():
    fired = []
    scores = {100: 50, 200: 75, 250: 80, 260: 95, 300: 92, 600: 91}
    a = RealtimeAlerter(emit=fired.append, scorer=_make_scorer(scores), debounce_blocks=300)
    for b in [100, 200, 250, 260, 300, 600]:
        a.ingest({"block_number": b})
    # emits: 200 (→YELLOW), 260 (→RED rising), 600 (cooled). Not 250/300 (within debounce).
    blocks = [x["block_number"] for x in fired]
    assert blocks == [200, 260, 600]


def test_emitted_alert_conforms_schema():
    fired = []
    a = RealtimeAlerter(emit=fired.append, scorer=_make_scorer({10: 93}))
    a.ingest({"block_number": 10})
    assert len(fired) == 1
    jsonschema.validate(fired[0], _SCHEMA)


def test_current_score_tracked():
    a = RealtimeAlerter(scorer=_make_scorer({5: 88}))
    a.ingest({"block_number": 5})
    assert a.current_score == 88
