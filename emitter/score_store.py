"""Rolling score history (Story 3.3, FR16).

Keeps a bounded timeline of scores for GET /history and the dashboard.
"""
import time
from collections import deque


class ScoreStore:
    def __init__(self, maxlen=20000):
        self._history = deque(maxlen=maxlen)

    def append(self, score, *, block_number=None, alert_level=None, timestamp=None, rcs=None):
        self._history.append({
            "timestamp": float(timestamp if timestamp is not None else time.time()),
            "block_number": block_number,
            "score": float(score),
            "alert_level": alert_level,
            "rcs": rcs or [],
        })

    def latest(self):
        return self._history[-1] if self._history else None

    def history(self, n=None):
        items = list(self._history)
        return items[-n:] if n else items

    def __len__(self):
        return len(self._history)
