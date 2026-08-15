"""Async webhook fan-out (Story 3.2, FR15).

Posts an alert payload to all subscriber URLs concurrently. Uses asyncio + a threaded
`requests.post` by default (no extra async-HTTP dependency); the sender is injectable
for testing. Failures are captured per-URL, never raised — one bad subscriber must not
block the others.
"""
import asyncio

import requests


def _default_sender(url, payload, timeout):
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return url, r.status_code, None
    except Exception as exc:  # network / timeout — report, don't raise
        return url, None, str(exc)


async def _post_one(url, payload, sender, timeout):
    return await asyncio.to_thread(sender, url, payload, timeout)


async def fan_out(urls, payload, *, sender=None, timeout=5.0):
    """POST payload to every url concurrently. Returns list of (url, status, error)."""
    sender = sender or _default_sender
    if not urls:
        return []
    return list(await asyncio.gather(*[_post_one(u, payload, sender, timeout) for u in urls]))


def fan_out_sync(urls, payload, *, sender=None, timeout=5.0):
    """Blocking convenience wrapper around fan_out (for non-async callers)."""
    return asyncio.run(fan_out(urls, payload, sender=sender, timeout=timeout))
