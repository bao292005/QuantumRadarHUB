"""Extract on-chain fixtures from Etherscan V2 logs API (Story 2.2, FR8/FR9).

Fetches logs for the 13-contract universe, decodes raw logs into the 11-field tick
schema (contracts/tick_data.schema.json), and writes gzip CSV to fixtures/backtest/.

Contract addresses, topic0 signatures, decode offsets, and fixture block ranges are
sourced from docs/04_DATA_GUIDE.md. Aave version is chosen by era (FR9); Compound
topic0 are computed via keccak, never guessed.

Usage:
    python3 -m tools.extract_fixtures --period all
    python3 -m tools.extract_fixtures --period luna_2022_05_09
"""
import argparse
import csv
import gzip
import os
import sys
import time
from pathlib import Path

import requests
from eth_utils import keccak

from ingestion.csv_loader import FIELDS

# --------------------------------------------------------------------------- #
# Configuration (docs/04_DATA_GUIDE.md)
# --------------------------------------------------------------------------- #
ETHERSCAN_URL = "https://api.etherscan.io/v2/api"
CHAIN_ID = 1
AAVE_V3_ERA_BLOCK = 16_493_000  # blocks < this → Aave V2, else Aave V3 (FR9)
PAGE_CAP = 1000                 # Etherscan max rows/call → chunk when hit

TOKENS = {
    "WETH": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
    "USDC": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "USDT": "0xdac17f958d2ee523a2206206994597c13d831ec7",
    "DAI": "0x6b175474e89094c44da98b954eedeac495271d0f",
    "WBTC": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
    "stETH": "0xae7ab96520de3a18e5e111b5eaab095312d7fe84",
    "UNI": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
}

# Uniswap V3 pools (9): (address, token0, token1)
UNI_POOLS = [
    ("0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640", "USDC", "WETH"),
    ("0x4e68ccd3e89f51c3074ca5072bbac773960dfa36", "WETH", "USDT"),
    ("0xcbcdf9626bc03e24f779434178a73a0b4bad62ed", "WBTC", "WETH"),
    ("0x109830a1aaad605bbf02a9dfa7b0b92ec2fb7daa", "stETH", "WETH"),
    ("0x5777d92f208679db4b9778590fa3cab3ac9e2168", "DAI", "USDC"),
    ("0x3416cf6c708da44db2624d63ea0aaef7113527c6", "USDC", "USDT"),
    ("0x99ac8ca7087fa4a2a1fb6357269965a2014abc35", "WBTC", "USDC"),
    ("0xc2e9f25be6257c210d7adf0d4cd6e3e881ba25f8", "DAI", "WETH"),
    ("0x1d42064fc4beb5f8aaf85f4617ae8b3b5b8bd801", "UNI", "WETH"),
]

AAVE_V2 = "0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9"
AAVE_V3 = "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"
SPARK = "0xc13e21b648a5ee794902342038ff3adab66be987"

# Compound V2 cTokens: (address, underlying symbol)
COMPOUND = [
    ("0x4ddc2d193948926d02f9b1fe9e1daa0718270ed5", "WETH"),  # cETH
    ("0x39aa39c021dfbae8fac545936693ac917d5e7563", "USDC"),  # cUSDC
    ("0x5d3a536e4d6dbd6114cc1ead35777bab948e3643", "DAI"),   # cDAI
    ("0xccf4429db6322d5c611ee964527d42e5d685dd6a", "WBTC"),  # cWBTC2
]

# topic0 signatures (docs/04_DATA_GUIDE.md)
SWAP_TOPIC = "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67"
AAVE_V2_BORROW = "0xc6a898309e823ee50bac64e45ca8adba6690e99e7841c45d754e2a38e9019d9b"
AAVE_V2_DEPOSIT = "0xde6857219544bb5b7746f48ed30be6386fefc61b2f864cacf559893bf50fd951"
AAVE_V3_BORROW = "0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0"
AAVE_V3_SUPPLY = "0x2b627736bca15cd5381dcf80b0bf11fd197d01a037c52b927a881a10fb73ba61"
AAVE_V3_WITHDRAW = "0x3115d1449a7b732c986cba18244e897a450f61e1bb8d589cd2e69e6c8924f9f7"
AAVE_LIQUIDATION = "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286"


def _topic(signature: str) -> str:
    """Compute event topic0 = keccak256(signature) (Compound events, FR9)."""
    return "0x" + keccak(text=signature).hex()


CMP_MINT = _topic("Mint(address,uint256,uint256)")
CMP_BORROW = _topic("Borrow(address,uint256,uint256,uint256)")
CMP_REDEEM = _topic("Redeem(address,uint256,uint256)")
CMP_LIQUIDATE = _topic("LiquidateBorrow(address,address,uint256,address,uint256)")

# Fixture block ranges + cascade block (docs/04_DATA_GUIDE.md)
FIXTURES = {
    "luna_2022_05_09": (14_724_000, 14_740_000, 14_732_113),
    "ftx_2022_11_08": (15_900_000, 15_925_000, 15_914_506),
    "normal_2023_03_15": (16_820_000, 16_825_000, None),
    "steth_depeg_2022_06": (14_940_000, 15_010_000, 14_975_000),
    "may_2021_eth_crash": (12_440_000, 12_500_000, 12_460_000),
    "wbtc_cascade_2022_06": (14_950_000, 15_010_000, 14_970_000),
    "eth_cascade_ftx_week_2022_11": (15_910_000, 15_965_000, 15_928_000),
    "usdc_depeg_2023_03": (16_790_000, 16_822_000, 16_802_000),
    "busd_freeze_2023_02": (16_590_000, 16_660_000, 16_615_000),
    "crv_near_miss_2023_08": (17_820_000, 17_880_000, None),
    "crv_near_miss_2023_11": (18_510_000, 18_630_000, None),
    "euler_hack_2023_03": (16_800_000, 16_835_000, 16_817_996),
}


# --------------------------------------------------------------------------- #
# Decode helpers (docs/04_DATA_GUIDE.md "Decode logic")
# --------------------------------------------------------------------------- #
def _int_from_hex(h, *, signed=False, bits=256):
    n = int(h, 16)
    if signed and n >= (1 << (bits - 1)):
        n -= (1 << bits)
    return n


def _slice_data(data_hex, offset):
    """32-byte word at `offset` (0-indexed); returns '0x0' if out of range."""
    start = 2 + offset * 64
    word = data_hex[start:start + 64]
    return "0x" + word if len(word) == 64 else "0x0"


def decode_amounts(protocol, event_type, data_hex):
    """Return (amount0, amount1) as python ints from the log data words.

    Offsets per docs/04_DATA_GUIDE.md:
      uniswap swap        -> amount0=word0(signed), amount1=word1(signed)
      aave borrow/supply  -> amount=word1
      aave withdraw       -> amount=word0 (reserve/user/to all indexed)
      aave liquidation    -> amount0=word1, amount1=word0
      compound mint/borrow/redeem -> amount=word1
      compound liquidation -> repay=word2, seize=word4
    """
    def W(i, signed=False):
        return _int_from_hex(_slice_data(data_hex, i), signed=signed)

    try:
        if protocol == "uniswap_v3":
            return W(0, True), W(1, True)
        if protocol in ("aave_v2", "aave_v3", "spark"):
            if event_type == "liquidation":
                return W(1), W(0)
            if event_type == "withdraw":
                return W(0), 0
            return W(1), 0  # borrow / supply
        if protocol == "compound_v2":
            if event_type == "liquidation":
                return W(2), W(4)
            return W(1), 0  # mint / borrow / withdraw(redeem)
    except (ValueError, IndexError):
        return 0, 0
    return 0, 0


def subscriptions_for(from_block):
    """Build (address, protocol, event_type, topic0, token0, token1) list for an era."""
    subs = []
    for addr, t0, t1 in UNI_POOLS:
        subs.append((addr, "uniswap_v3", "swap", SWAP_TOPIC, t0, t1))
    for addr, underlying in COMPOUND:
        subs.append((addr, "compound_v2", "mint", CMP_MINT, underlying, ""))
        subs.append((addr, "compound_v2", "borrow", CMP_BORROW, underlying, ""))
        subs.append((addr, "compound_v2", "withdraw", CMP_REDEEM, underlying, ""))  # redeem→withdraw
        subs.append((addr, "compound_v2", "liquidation", CMP_LIQUIDATE, underlying, ""))
    if from_block < AAVE_V3_ERA_BLOCK:
        subs.append((AAVE_V2, "aave_v2", "borrow", AAVE_V2_BORROW, "", ""))
        subs.append((AAVE_V2, "aave_v2", "supply", AAVE_V2_DEPOSIT, "", ""))  # deposit→supply
        subs.append((AAVE_V2, "aave_v2", "liquidation", AAVE_LIQUIDATION, "", ""))
    else:
        for a3, proto in ((AAVE_V3, "aave_v3"), (SPARK, "spark")):
            subs.append((a3, proto, "borrow", AAVE_V3_BORROW, "", ""))
            subs.append((a3, proto, "supply", AAVE_V3_SUPPLY, "", ""))
            subs.append((a3, proto, "withdraw", AAVE_V3_WITHDRAW, "", ""))
            subs.append((a3, proto, "liquidation", AAVE_LIQUIDATION, "", ""))
    return subs


# --------------------------------------------------------------------------- #
# Etherscan fetch (chunked, rate-limited)
# --------------------------------------------------------------------------- #
def _load_env_key():
    key = os.environ.get("ETHERSCAN_API_KEY")
    if key:
        return key
    env = Path(__file__).parents[1] / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line.startswith("ETHERSCAN_API_KEY"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _call(session, address, topic0, lo, hi, api_key, throttle):
    params = {
        "chainid": CHAIN_ID, "module": "logs", "action": "getLogs",
        "fromBlock": lo, "toBlock": hi, "address": address,
        "topic0": topic0, "offset": PAGE_CAP, "page": 1, "apikey": api_key,
    }
    for attempt in range(4):
        time.sleep(throttle)
        try:
            r = session.get(ETHERSCAN_URL, params=params, timeout=30)
            data = r.json()
        except Exception as exc:  # network/JSON errors → retry
            time.sleep(1.0 + attempt)
            continue
        result = data.get("result")
        if isinstance(result, list):
            return result
        msg = str(data.get("message", "")) + " " + str(result)
        if "No records found" in msg:
            return []
        if "rate limit" in msg.lower() or "Max" in msg:
            time.sleep(1.0 + attempt)
            continue
        return []  # unknown non-list result
    return []


def fetch_logs(session, address, topic0, lo, hi, api_key, throttle):
    """Fetch all logs in [lo, hi], recursively splitting ranges that hit PAGE_CAP."""
    out, stack = [], [(lo, hi)]
    while stack:
        a, b = stack.pop()
        res = _call(session, address, topic0, a, b, api_key, throttle)
        if len(res) >= PAGE_CAP and b > a:
            mid = (a + b) // 2
            stack.append((mid + 1, b))
            stack.append((a, mid))
        else:
            out.extend(res)
    return out


def _log_to_tick(log, protocol, event_type, pool_address, token0, token1):
    a0, a1 = decode_amounts(protocol, event_type, log.get("data", "0x"))
    return {
        "block_number": int(log["blockNumber"], 16),
        "block_timestamp": int(log["timeStamp"], 16),
        "protocol": protocol,
        "event_type": event_type,
        "pool_address": pool_address.lower(),
        "token0": token0,
        "token1": token1,
        "amount0": str(a0),
        "amount1": str(a1),
        "tx_hash": log["transactionHash"],
        "log_index": int(log["logIndex"], 16),
    }


def extract_period(name, out_dir, api_key, throttle):
    if name not in FIXTURES:
        raise KeyError(f"unknown fixture: {name}")
    lo, hi, _cascade = FIXTURES[name]
    subs = subscriptions_for(lo)
    session = requests.Session()
    rows = []
    for i, (addr, proto, etype, topic0, t0, t1) in enumerate(subs, 1):
        logs = fetch_logs(session, addr, topic0, lo, hi, api_key, throttle)
        for lg in logs:
            try:
                rows.append(_log_to_tick(lg, proto, etype, addr, t0, t1))
            except (KeyError, ValueError):
                continue
        print(f"  [{i}/{len(subs)}] {proto}/{etype} {addr[:10]}… → {len(logs)} logs",
              file=sys.stderr)
    rows.sort(key=lambda e: (e["block_number"], e["log_index"]))

    out_path = Path(out_dir) / f"{name}.csv.gz"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wt", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"✓ {name}: {len(rows)} rows → {out_path}", file=sys.stderr)
    return out_path, len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extract QuantumRadar fixtures from Etherscan")
    ap.add_argument("--period", default="all", help="fixture name or 'all'")
    ap.add_argument("--out-dir", default="fixtures/backtest")
    ap.add_argument("--throttle", type=float, default=0.25, help="seconds between API calls")
    args = ap.parse_args(argv)

    api_key = _load_env_key()
    if not api_key:
        print("ERROR: ETHERSCAN_API_KEY not found (env or .env)", file=sys.stderr)
        return 2

    periods = list(FIXTURES) if args.period == "all" else [args.period]
    for name in periods:
        print(f"→ extracting {name}", file=sys.stderr)
        extract_period(name, args.out_dir, api_key, args.throttle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
