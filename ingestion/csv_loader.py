"""Load gzip CSV fixtures into normalized tick-event dicts (Story 2.1, FR10).

CSV columns follow the 11-field order in contracts/tick_data.schema.json.
amount0/1 stay as strings (wei precision); integer fields are cast to int so
downstream (engine/cfi/onchain.py) can bisect/compare block_number directly.
"""
import csv
import gzip
from typing import Iterator, List, Dict

FIELDS = [
    "block_number", "block_timestamp", "protocol", "event_type", "pool_address",
    "token0", "token1", "amount0", "amount1", "tx_hash", "log_index",
]
_INT_FIELDS = ("block_number", "block_timestamp", "log_index")


def _coerce(row: Dict[str, str]) -> Dict:
    event = {k: (row.get(k) or "") for k in FIELDS}
    for k in _INT_FIELDS:
        raw = event[k]
        event[k] = int(raw) if str(raw).strip() != "" else 0
    return event


def iter_csv_events(path: str) -> Iterator[Dict]:
    """Yield normalized event dicts from a gzip CSV fixture, one per row."""
    with gzip.open(path, "rt", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            yield _coerce(row)


def load_events(path: str) -> List[Dict]:
    """Eager list of events, sorted by (block_number, log_index) for windowing."""
    events = list(iter_csv_events(path))
    events.sort(key=lambda e: (e["block_number"], e["log_index"]))
    return events
