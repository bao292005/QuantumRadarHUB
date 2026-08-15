"""On-chain ETH price + forward-drawdown labels (objective ground truth for F1).

Price is derived from the USDC/WETH Uniswap pool we already extract (no external
feed). A scoring window is labelled POSITIVE if ETH price drops >= DRAWDOWN_PCT
within HORIZON_HOURS forward — objective and uniform across all fixtures, replacing
hand-picked cascade blocks. Windows without a full forward horizon are UNLABELLED
(None) and excluded from F1 (you cannot know the future at the tail of a fixture).
"""
import bisect
from statistics import median

from engine.scoring import WINDOW_BLOCKS, STRIDE_BLOCKS
from tools._common import window_end_blocks, SECONDS_PER_BLOCK

USDC_WETH_POOL = "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"
USDC_DECIMALS = 6
WETH_DECIMALS = 18

DRAWDOWN_PCT = 0.10      # >= 10% drop = stress
HORIZON_HOURS = 48.0     # forward look-ahead


def _swap_price(e):
    """USDC per WETH from a USDC/WETH swap; None if unusable."""
    try:
        a0 = abs(float(e["amount0"]))  # USDC leg (token0)
        a1 = abs(float(e["amount1"]))  # WETH leg (token1)
    except (TypeError, ValueError):
        return None
    if a0 == 0 or a1 == 0:
        return None
    return (a0 / 10 ** USDC_DECIMALS) / (a1 / 10 ** WETH_DECIMALS)


def window_price_series(events):
    """Per activity-window ETH price (median of USDC/WETH swaps), forward-filled.

    Returns (ends, prices) aligned to window_end_blocks; prices[k] may be None only
    if no swap has occurred up to window k yet.
    """
    ends = window_end_blocks(events)
    swaps = []
    for e in events:
        if e.get("event_type") != "swap":
            continue
        if e.get("pool_address", "").lower() != USDC_WETH_POOL:
            continue
        p = _swap_price(e)
        if p is not None:
            swaps.append((e["block_number"], p))
    swaps.sort(key=lambda x: x[0])
    blocks = [b for b, _ in swaps]

    prices, last = [], None
    for end in ends:
        lo = end - WINDOW_BLOCKS
        li = bisect.bisect_right(blocks, lo)
        ri = bisect.bisect_right(blocks, end)
        win = [swaps[j][1] for j in range(li, ri)]
        if win:
            last = float(median(win))
        prices.append(last)  # forward-fill last known price
    return ends, prices


def window_ohlc(events):
    """Per activity-window OHLC of ETH price (USDC/WETH). Flat doji forward-filled.

    Returns (ends, ohlc) aligned to window_end_blocks; each ohlc entry is
    {"o","h","l","c"} or None until the first swap is seen.
    """
    ends = window_end_blocks(events)
    swaps = []
    for e in events:
        if e.get("event_type") != "swap":
            continue
        if e.get("pool_address", "").lower() != USDC_WETH_POOL:
            continue
        p = _swap_price(e)
        if p is not None:
            swaps.append((e["block_number"], p))
    swaps.sort(key=lambda x: x[0])
    blocks = [b for b, _ in swaps]

    ohlc, last_close = [], None
    for end in ends:
        lo = end - WINDOW_BLOCKS
        li = bisect.bisect_right(blocks, lo)
        ri = bisect.bisect_right(blocks, end)
        win = [swaps[j][1] for j in range(li, ri)]
        if win:
            last_close = win[-1]
            ohlc.append({"o": round(win[0], 2), "h": round(max(win), 2),
                         "l": round(min(win), 2), "c": round(win[-1], 2)})
        elif last_close is not None:
            v = round(last_close, 2)
            ohlc.append({"o": v, "h": v, "l": v, "c": v})  # flat doji
        else:
            ohlc.append(None)
    return ends, ohlc


def forward_drawdown_labels(events, scored_blocks, *,
                            drawdown_pct=DRAWDOWN_PCT, horizon_hours=HORIZON_HOURS,
                            fit_window=40):
    """Label each scored window: 1 (stress), 0 (calm), or None (no forward horizon).

    scored_blocks[i] is the block at the end of scored window i. Positive if the min
    forward price within horizon drops >= drawdown_pct below the current price.
    """
    ends, prices = window_price_series(events)
    if not ends:
        return [None] * len(scored_blocks)
    horizon_blocks = int(horizon_hours * 3600 / SECONDS_PER_BLOCK)
    max_end = ends[-1]

    labels = []
    for b in scored_blocks:
        # current price = price of the window whose end is nearest <= b
        k = bisect.bisect_right(ends, b) - 1
        cur = prices[k] if 0 <= k < len(prices) else None
        if cur is None:
            labels.append(None)
            continue
        if b + horizon_blocks > max_end:
            labels.append(None)  # incomplete forward horizon → cannot label
            continue
        future = [prices[j] for j, e in enumerate(ends)
                  if b < e <= b + horizon_blocks and prices[j] is not None]
        if not future:
            labels.append(None)
            continue
        dd = (min(future) - cur) / cur
        labels.append(1 if dd <= -drawdown_pct else 0)
    return labels
