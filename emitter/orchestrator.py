"""RealtimeAlerter — stream events → score → debounce → emit (Story 3.1, FR14).

Wraps the VERBATIM core with a rolling event window. Needs ~4500 blocks of history
(FIT_WINDOW return-windows) to warm up; emits an alert only on a rising level change
or after a debounce cooldown, never every block.
"""
from collections import deque

from engine.cfi.onchain import active_contracts, build_returns_matrix
from engine.mps.v2 import mps_correlation_score, rcs_scores
from engine.scoring import (
    score_100, alert_level, FIT_WINDOW, WINDOW_BLOCKS, STRIDE_BLOCKS,
)
from emitter.payload import format_alert

# History needed: FIT_WINDOW return-windows (+2 slack) × stride + one window span.
CFI_MIN_HISTORY = (FIT_WINDOW + 2) * STRIDE_BLOCKS + WINDOW_BLOCKS  # ≈ 4500
MIN_WINDOWS_ACTIVE = 3


def cfi_mps_score(events, *, min_windows_active=MIN_WINDOWS_ACTIVE):
    """(score_100, rcs_dict) from the most-recent FIT_WINDOW return-windows."""
    contracts = active_contracts(
        events, min_windows_active=min_windows_active,
        window_blocks=WINDOW_BLOCKS, stride_blocks=STRIDE_BLOCKS)
    if len(contracts) < 2:
        return 0.0, {}
    R = build_returns_matrix(events, contracts, window_blocks=WINDOW_BLOCKS, stride_blocks=STRIDE_BLOCKS)
    if R.shape[1] < FIT_WINDOW + 1:
        return 0.0, {}
    window = R[:, -FIT_WINDOW:]
    score = round(score_100(mps_correlation_score(window)), 2)
    rcs = rcs_scores(window, contracts) if score >= 50 else {}
    return score, rcs


class RealtimeAlerter:
    """Ingest events one/many at a time; emit debounced fragility alerts."""

    def __init__(self, emit=None, scorer=None, *, min_history=CFI_MIN_HISTORY, debounce_blocks=300):
        self.emit = emit or (lambda alert: None)
        self.scorer = scorer or cfi_mps_score
        self.min_history = min_history
        self.debounce_blocks = debounce_blocks
        self.events = deque()
        self.current_score = 0.0
        self.current_rcs = {}
        self._last_level = None
        self._last_emit_block = None

    def ingest(self, event):
        """Add one event, prune stale history, re-score, maybe emit. Returns alert or None."""
        self.events.append(event)
        latest = event["block_number"]
        while self.events and self.events[0]["block_number"] < latest - self.min_history:
            self.events.popleft()
        return self._evaluate(latest)

    def ingest_many(self, events):
        alert = None
        for e in events:
            a = self.ingest(e)
            if a is not None:
                alert = a
        return alert

    def _evaluate(self, block):
        score, rcs = self.scorer(list(self.events))
        self.current_score, self.current_rcs = score, rcs
        level = alert_level(score)

        alert = None
        if level is not None:
            rising = level != self._last_level
            cooled = (self._last_emit_block is None
                      or block - self._last_emit_block >= self.debounce_blocks)
            if rising or cooled:
                alert = format_alert(score, rcs, block)
                if alert is not None:
                    self.emit(alert)
                    self._last_emit_block = block
        self._last_level = level
        return alert
