"""Story 3.1 tests — payload + orchestrator persistence/hysteresis (mock scorer)."""
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


# ---- orchestrator persistence + hysteresis ----
def _make_scorer(score_by_block):
    def scorer(events):
        return score_by_block.get(events[-1]["block_number"], 0.0), {"0xa": 0.1}
    return scorer


def _run(alerter, blocks):
    for b in blocks:
        alerter.ingest({"block_number": b})


def test_single_red_spike_is_filtered():
    fired = []
    scores = {100: 50, 200: 95, 300: 50, 400: 50}  # only 1 RED window
    a = RealtimeAlerter(emit=fired.append, scorer=_make_scorer(scores), persistence=4)
    _run(a, [100, 200, 300, 400])
    assert fired == []  # a lone spike must not fire


def test_sustained_red_fires_after_N_windows():
    fired = []
    scores = {b: 95 for b in (100, 200, 300, 400, 500)}
    a = RealtimeAlerter(emit=fired.append, scorer=_make_scorer(scores), persistence=4)
    _run(a, [100, 200, 300, 400, 500])
    # fires only when the 4th consecutive RED window is reached (block 400)
    assert [x["block_number"] for x in fired] == [400]
    assert a.alert_on is True


def test_hysteresis_holds_through_dip_then_clears():
    scores = {100: 95, 200: 95, 300: 95, 400: 95, 500: 75, 600: 60}
    a = RealtimeAlerter(scorer=_make_scorer(scores), persistence=4)
    _run(a, [100, 200, 300, 400])
    assert a.alert_on is True
    a.ingest({"block_number": 500})   # dip to 75 (>= clear 70) → stays ON
    assert a.alert_on is True
    a.ingest({"block_number": 600})   # drop to 60 (< clear) → clears
    assert a.alert_on is False


def test_persistence_one_fires_immediately():
    fired = []
    a = RealtimeAlerter(emit=fired.append, scorer=_make_scorer({100: 95}), persistence=1)
    a.ingest({"block_number": 100})
    assert [x["block_number"] for x in fired] == [100]


def test_emitted_alert_conforms_schema():
    fired = []
    scores = {b: 93 for b in (100, 200, 300, 400)}
    a = RealtimeAlerter(emit=fired.append, scorer=_make_scorer(scores), persistence=4)
    _run(a, [100, 200, 300, 400])
    assert len(fired) == 1
    jsonschema.validate(fired[0], _SCHEMA)


def test_current_score_tracked():
    a = RealtimeAlerter(scorer=_make_scorer({500: 88}))
    a.ingest({"block_number": 500})
    assert a.current_score == 88
