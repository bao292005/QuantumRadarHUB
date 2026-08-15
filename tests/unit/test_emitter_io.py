"""Story 3.2 tests — subscriber registry persistence + webhook fan-out."""
import asyncio

import pytest

from emitter.registry import SubscriberRegistry
from emitter.webhook import fan_out, fan_out_sync


# ---- registry ----
def test_add_dedup_and_list(tmp_path):
    reg = SubscriberRegistry(tmp_path / "subs.json")
    assert reg.add("http://a/hook") is True
    assert reg.add("http://a/hook") is False  # dedup
    assert reg.add("http://b/hook") is True
    assert reg.list() == ["http://a/hook", "http://b/hook"]


def test_remove(tmp_path):
    reg = SubscriberRegistry(tmp_path / "subs.json")
    reg.add("http://a/hook")
    assert reg.remove("http://a/hook") is True
    assert reg.remove("http://a/hook") is False
    assert reg.list() == []


def test_persistence_across_reload(tmp_path):
    p = tmp_path / "subs.json"
    SubscriberRegistry(p).add("http://persist/hook")
    assert SubscriberRegistry(p).list() == ["http://persist/hook"]


# ---- webhook fan-out ----
def test_fan_out_hits_all_subscribers():
    calls = []

    def fake_sender(url, payload, timeout):
        calls.append((url, payload))
        return url, 200, None

    urls = ["http://a/h", "http://b/h", "http://c/h"]
    results = asyncio.run(fan_out(urls, {"score": 95}, sender=fake_sender))
    assert len(results) == 3
    assert {u for u, _ in calls} == set(urls)
    assert all(status == 200 for _, status, _ in results)


def test_fan_out_isolates_failures():
    def flaky(url, payload, timeout):
        if "bad" in url:
            return url, None, "boom"
        return url, 200, None

    results = fan_out_sync(["http://ok/h", "http://bad/h"], {"x": 1}, sender=flaky)
    by_url = {u: (s, e) for u, s, e in results}
    assert by_url["http://ok/h"][0] == 200
    assert by_url["http://bad/h"][1] == "boom"  # failure captured, not raised


def test_fan_out_empty():
    assert asyncio.run(fan_out([], {"x": 1})) == []
