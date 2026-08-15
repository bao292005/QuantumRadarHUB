# Data Guide — Fixtures & Extraction

## Nguồn dữ liệu

**Etherscan V2 logs API** (free tier, 3 req/s). Endpoint:
```
https://api.etherscan.io/v2/api?chainid=1&module=logs&action=getLogs
   &fromBlock=X&toBlock=Y&address=<contract>&topic0=<event>&apikey=<key>
```
Trả tối đa 1000 rows/call → chunk block range khi vượt.

---

## 13-contract universe (whitelist)

### Uniswap V3 pools (9)
| Pool | token0 | token1 | Address |
|------|--------|--------|---------|
| USDC/WETH 0.05% | USDC | WETH | `0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640` |
| WETH/USDT 0.3% | WETH | USDT | `0x4e68ccd3e89f51c3074ca5072bbac773960dfa36` |
| WBTC/WETH 0.3% | WBTC | WETH | `0xcbcdf9626bc03e24f779434178a73a0b4bad62ed` |
| stETH/WETH 0.01% | stETH | WETH | `0x109830a1aaad605bbf02a9dfa7b0b92ec2fb7daa` |
| DAI/USDC 0.01% | DAI | USDC | `0x5777d92f208679db4b9778590fa3cab3ac9e2168` |
| USDC/USDT 0.01% | USDC | USDT | `0x3416cf6c708da44db2624d63ea0aaef7113527c6` |
| WBTC/USDC 0.3% | WBTC | USDC | `0x99ac8ca7087fa4a2a1fb6357269965a2014abc35` |
| DAI/WETH 0.3% | DAI | WETH | `0xc2e9f25be6257c210d7adf0d4cd6e3e881ba25f8` |
| UNI/WETH 0.3% | UNI | WETH | `0x1d42064fc4beb5f8aaf85f4617ae8b3b5b8bd801` |

### Lending
| Protocol | Address |
|----------|---------|
| Aave V2 | `0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9` |
| Aave V3 | `0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2` |
| Spark | `0xc13e21b648a5ee794902342038ff3adab66be987` |
| cETH | `0x4ddc2d193948926d02f9b1fe9e1daa0718270ed5` (underlying WETH) |
| cUSDC | `0x39aa39c021dfbae8fac545936693ac917d5e7563` (underlying USDC) |
| cDAI | `0x5d3a536e4d6dbd6114cc1ead35777bab948e3643` (underlying DAI) |
| cWBTC2 | `0xccf4429db6322d5c611ee964527d42e5d685dd6a` (underlying WBTC) |

### Token addresses
```
WETH  0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2
USDC  0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
USDT  0xdac17f958d2ee523a2206206994597c13d831ec7
DAI   0x6b175474e89094c44da98b954eedeac495271d0f
WBTC  0x2260fac5e5542a773aa44fbcfedf7c193bc2c599
stETH 0xae7ab96520de3a18e5e111b5eaab095312d7fe84
UNI   0x1f9840a85d5af5bf1d1762f925bdaddc4201f984
```

---

## Event topic0 (keccak256 signatures)

```
# Uniswap V3
SWAP        0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67

# Aave V2
BORROW      0xc6a898309e823ee50bac64e45ca8adba6690e99e7841c45d754e2a38e9019d9b
DEPOSIT     0xde6857219544bb5b7746f48ed30be6386fefc61b2f864cacf559893bf50fd951

# Aave V3 + Spark (identical ABI)
BORROW      0xb3d084820fb1a9decffb176436bd02558d15fac9b0ddfed8c465bc7359d7dce0
SUPPLY      0x2b627736bca15cd5381dcf80b0bf11fd197d01a037c52b927a881a10fb73ba61
WITHDRAW    0x3115d1449a7b732c986cba18244e897a450f61e1bb8d589cd2e69e6c8924f9f7

# Aave V2 & V3 share LiquidationCall
LIQUIDATION 0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286

# Compound V2 (computed: keccak(text=signature))
MINT        keccak("Mint(address,uint256,uint256)")
BORROW      keccak("Borrow(address,uint256,uint256,uint256)")
REDEEM      keccak("Redeem(address,uint256,uint256)")
LIQUIDATE   keccak("LiquidateBorrow(address,address,uint256,address,uint256)")
```

---

## Normalized tick schema (11 fields)

Mỗi event → dict:
```
block_number, block_timestamp, protocol, event_type, pool_address,
token0, token1, amount0, amount1, tx_hash, log_index
```
- `protocol`: uniswap_v3 | aave_v2 | aave_v3 | spark | compound_v2
- `event_type`: swap | mint | burn | borrow | supply | withdraw | liquidation
- `amount0/1`: decimal string (wei precision, signed cho swap)

**Chỉ cần `pool_address` + `amount0` cho CFI+MPS** (activity = Σ|amount0| per contract).

---

## 12 fixtures (đã extract, blocks + cascade)

| Fixture | Block range | Cascade block | Type | Rows |
|---------|-------------|---------------|------|------|
| luna_2022_05_09 | 14,724,000–14,740,000 | 14,732,113 | crisis | 32k |
| ftx_2022_11_08 | 15,900,000–15,925,000 | 15,914,506 | crisis | 46k |
| normal_2023_03_15 | 16,820,000–16,825,000 | — | FP control | 12k |
| steth_depeg_2022_06 | 14,940,000–15,010,000 | 14,975,000 | crisis | 228k |
| may_2021_eth_crash | 12,440,000–12,500,000 | 12,460,000 | crisis | 93k |
| wbtc_cascade_2022_06 | 14,950,000–15,010,000 | 14,970,000 | crisis | 203k |
| eth_cascade_ftx_week | 15,910,000–15,965,000 | 15,928,000 | crisis | 183k |
| usdc_depeg_2023_03 | 16,790,000–16,822,000 | 16,802,000 | depeg | 106k |
| busd_freeze_2023_02 | 16,590,000–16,660,000 | 16,615,000 | FP control | 121k |
| crv_near_miss_2023_08 | 17,820,000–17,880,000 | — | near-miss | 49k |
| crv_near_miss_2023_11 | 18,510,000–18,630,000 | — | near-miss | 134k |
| euler_hack_2023_03 | 16,800,000–16,835,000 | 16,817,996 | FP control | 114k |

**Aave version by era:** blocks < 16,493,000 (Jan 2023) → Aave V2; sau → Aave V3.

---

## Extraction command

```bash
# Cần .env với ETHERSCAN_API_KEY
python3 -m tools.extract_fixtures --period all          # cả 12
python3 -m tools.extract_fixtures --period steth_depeg  # 1 cái
```

Output: `fixtures/backtest/<name>.csv.gz` (gzip CSV, header + rows).

---

## Decode logic (raw Etherscan log → tick dict)

```python
def _int_from_hex(h, *, signed=False, bits=256):
    n = int(h, 16)
    if signed and n >= (1 << (bits-1)): n -= (1 << bits)
    return n

def _slice_data(data_hex, offset):  # 32-byte word at offset
    return "0x" + data_hex[2 + offset*64 : 2 + offset*64 + 64]

# Uniswap swap: amount0=word0(signed), amount1=word1(signed)
# Aave borrow: reserve=topic1→addr, amount=word1
# Aave liquidation: collateral=topic1, debt=topic2, amount0=word1, amount1=word0
# Compound borrow: borrower=word0, amount=word1
# Compound liquidation: repay=word2, seize=word4
```

Full decoder trong `tools/extract_fixtures.py`.

---

## Caveat data

- **stETH/WETH pool = 0 swaps** cho fixtures 2022 (pool ít activity) — bình thường
- **Spark = 0 rows** cho mọi fixture trước 2023 (deploy Jan 2023) — bình thường
- Block numbers là **ước tính** (trừ những cái verified); sai số ±0.5-1%. Verify bằng
  Etherscan `getblocknobytime` nếu cần chính xác.
- Compound V2 có indexed params khác nhau → topic0 phải compute bằng keccak, không
  đoán.
