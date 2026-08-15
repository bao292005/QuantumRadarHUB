"""Subscriber registry with JSON persistence (Story 3.2, FR16).

Stores webhook subscriber URLs; survives restart by round-tripping to a JSON file.
"""
import json
import threading
from pathlib import Path


class SubscriberRegistry:
    def __init__(self, path="subscribers.json"):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._subs = self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                if isinstance(data, list):
                    return list(dict.fromkeys(str(u) for u in data))
            except (json.JSONDecodeError, OSError):
                pass
        return []

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._subs, indent=2))

    def add(self, url):
        """Register a subscriber URL. Returns True if newly added."""
        url = str(url)
        with self._lock:
            if url in self._subs:
                return False
            self._subs.append(url)
            self._save()
            return True

    def remove(self, url):
        url = str(url)
        with self._lock:
            if url not in self._subs:
                return False
            self._subs.remove(url)
            self._save()
            return True

    def list(self):
        with self._lock:
            return list(self._subs)
