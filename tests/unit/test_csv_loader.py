"""Story 2.1 tests — csv_loader round-trip + schema conformance (FR10)."""
import csv
import gzip
import json
import gzip as _gz
from pathlib import Path

import jsonschema
import pytest

from ingestion.csv_loader import iter_csv_events, load_events, FIELDS

_SCHEMA = json.loads(
    (Path(__file__).parents[2] / "contracts" / "tick_data.schema.json").read_text()
)

_ROWS = [
    {
        "block_number": "14732000", "block_timestamp": "1652140000",
        "protocol": "uniswap_v3", "event_type": "swap",
        "pool_address": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
        "token0": "USDC", "token1": "WETH",
        "amount0": "-123456789012345678", "amount1": "987654321",
        "tx_hash": "0x" + "ab" * 32, "log_index": "5",
    },
    {
        "block_number": "14732050", "block_timestamp": "1652140600",
        "protocol": "aave_v2", "event_type": "liquidation",
        "pool_address": "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9",
        "token0": "DAI", "token1": "WETH",
        "amount0": "5000000000000000000", "amount1": "0",
        "tx_hash": "0x" + "cd" * 32, "log_index": "12",
    },
]


@pytest.fixture
def fixture_csv(tmp_path):
    p = tmp_path / "mini.csv.gz"
    with gzip.open(p, "wt", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(_ROWS)
    return str(p)


def test_iter_yields_all_rows(fixture_csv):
    events = list(iter_csv_events(fixture_csv))
    assert len(events) == 2


def test_events_have_11_fields(fixture_csv):
    for e in iter_csv_events(fixture_csv):
        assert set(e.keys()) == set(FIELDS)
        assert len(FIELDS) == 11


def test_int_fields_coerced(fixture_csv):
    e = next(iter_csv_events(fixture_csv))
    assert e["block_number"] == 14732000 and isinstance(e["block_number"], int)
    assert e["log_index"] == 5
    assert e["amount0"] == "-123456789012345678"  # kept as string (wei precision)


def test_conforms_to_schema(fixture_csv):
    for e in iter_csv_events(fixture_csv):
        jsonschema.validate(e, _SCHEMA)


def test_load_events_sorted(fixture_csv):
    events = load_events(fixture_csv)
    blocks = [e["block_number"] for e in events]
    assert blocks == sorted(blocks)
