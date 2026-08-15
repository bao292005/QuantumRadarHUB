"""Alert payload formatting (Story 3.1, FR15).

Builds a dict conforming to contracts/fragility_alert.schema.json. alert_level reuses
the LOCKED thresholds from engine.scoring (RED>=90 / YELLOW>=70).
"""
import time

from engine.scoring import alert_level

VERSION = "1"


def format_alert(score, rcs, block_number, *, timestamp=None, top_n=5, version=VERSION):
    """Format a fragility alert. Returns None if score is below YELLOW (no alert)."""
    level = alert_level(score)
    if level is None:
        return None
    if isinstance(rcs, dict):
        items = list(rcs.items())
    else:
        items = list(rcs or [])
    rcs_list = [{"contract": str(c), "contribution": float(v)} for c, v in items[:top_n]]
    return {
        "version": version,
        "timestamp": float(timestamp if timestamp is not None else time.time()),
        "block_number": int(block_number),
        "score": float(score),
        "alert_level": level,
        "rcs": rcs_list,
    }
