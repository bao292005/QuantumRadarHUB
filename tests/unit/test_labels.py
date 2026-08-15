"""Story (F1 extension) tests — forward liquidation-cascade labeler."""
from tools.labels import (
    forward_liquidation_counts, percentile_threshold, labels_from_counts,
)


def _ev(block, etype):
    return {"block_number": block, "event_type": etype}


# liquidations at 100,110,120,500; a swap that should be ignored; final marker at 1000
EVENTS = [
    _ev(100, "liquidation"), _ev(110, "liquidation"), _ev(120, "liquidation"),
    _ev(300, "swap"), _ev(500, "liquidation"), _ev(1000, "swap"),
]


def test_forward_counts_horizon_and_none_tail():
    # horizon_hours=1 → 3600/12 = 300 blocks forward
    counts = forward_liquidation_counts(EVENTS, [50, 400, 900], horizon_hours=1.0)
    assert counts == [3, 1, None]  # (50,350]→3 ; (400,700]→1 ; 900+300>1000→None


def test_forward_counts_ignore_non_liquidation():
    counts = forward_liquidation_counts(EVENTS, [290], horizon_hours=1.0)
    # (290,590] contains only liquidation @500 (swap @300 ignored)
    assert counts == [1]


def test_percentile_threshold_floor():
    assert percentile_threshold([3, 1], pct=50) == 2.0
    assert percentile_threshold([0, 0, 0], pct=90) == 1.0  # floored to min_count
    assert percentile_threshold([None, None]) is None


def test_labels_from_counts():
    assert labels_from_counts([3, 1, None], 2.0) == [1, 0, None]
    assert labels_from_counts([5, 2], None) == [None, None]
