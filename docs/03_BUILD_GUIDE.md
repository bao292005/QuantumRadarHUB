# Build Guide — 24h Recipe

Công thức build lại toàn bộ từ số 0 đến kết quả 7/7. Mỗi bước có lệnh chạy + file cần tạo.

---

## Phase 0 — Setup (Giờ 0-1)

```bash
# Python 3.11+ với anaconda (có sẵn numpy/torch/pydantic)
python3 -m venv venv || true
pip install numpy scikit-learn fastapi uvicorn requests pyyaml jsonschema pytest pytest-asyncio

# .env với Etherscan key
echo "ETHERSCAN_API_KEY=<your_key>" > .env
```

**Package structure cần tạo:**
```
engine/
  cfi/__init__.py  cfi/correlation.py  cfi/onchain.py
  mps/__init__.py  mps/v2.py
ingestion/
  csv_loader.py        # đọc gzip CSV fixtures
tools/
  extract_fixtures.py  # fetch từ Etherscan
  cfi_mps_calibrate.py # calibrate
  validate_10_scenarios.py
  honest_detection_count.py
fixtures/backtest/     # nơi chứa *.csv.gz
```

---

## Phase 1 — Core algorithm (Giờ 1-5)

Copy 3 file từ `02_ALGORITHM_SPEC.md`:
1. `engine/cfi/correlation.py` — spectral metrics (Ledoit-Wolf + eigenvalue entropy)
2. `engine/cfi/onchain.py` — activity/returns matrix builder
3. `engine/mps/v2.py` — `mps_correlation_score` + `rcs_scores` + `rolling_scores`

**Test ngay với synthetic data:**
```python
# test: synchronized returns → high score, uncorrelated → low
import numpy as np
from engine.mps.v2 import mps_correlation_score
rng = np.random.default_rng(42)
factor = rng.standard_normal(60)
sync = np.array([factor + 0.05*rng.standard_normal(60) for _ in range(8)])
uncorr = rng.standard_normal((8, 60))
assert mps_correlation_score(sync) > mps_correlation_score(uncorr)  # PHẢI pass
```

**Gate:** synchronized > uncorrelated. Nếu fail → sai công thức entropy.

---

## Phase 2 — Data extraction (Giờ 5-9, chạy background)

### 2a. Contract whitelist (13 contracts)

```python
# Uniswap V3 pools (9)
UNI_POOLS = [
  ("0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640", USDC, WETH),  # USDC/WETH 0.05%
  ("0x4e68ccd3e89f51c3074ca5072bbac773960dfa36", WETH, USDT),
  ("0xcbcdf9626bc03e24f779434178a73a0b4bad62ed", WBTC, WETH),
  ("0x5777d92f208679db4b9778590fa3cab3ac9e2168", DAI, USDC),
  ("0x3416cf6c708da44db2624d63ea0aaef7113527c6", USDC, USDT),
  ("0x99ac8ca7087fa4a2a1fb6357269965a2014abc35", WBTC, USDC),
  ("0xc2e9f25be6257c210d7adf0d4cd6e3e881ba25f8", DAI, WETH),
  ("0x1d42064fc4beb5f8aaf85f4617ae8b3b5b8bd801", UNI, WETH),
]
# Aave V2: 0x7d2768de32b0b80b7a3454c06bdac94a69ddc7a9
# Aave V3: 0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2
# Compound V2 cTokens: cETH cUSDC cDAI cWBTC2
```

Full addresses + topics trong `tools/extract_fixtures.py` (04_DATA_GUIDE.md).

### 2b. Extract 12 fixtures

```bash
# Background — mất ~15-20 phút cho cả 12
python3 -m tools.extract_fixtures --period all
```

**Token decimals + USD detection** (cho price nếu cần) — xem 04_DATA_GUIDE.md.

---

## Phase 3 — Calibration (Giờ 9-12)

```bash
# Chạy trên luna/ftx/normal → tìm SCORE_FLOOR/CEIL
python3 -m tools.cfi_mps_calibrate
```

**Cách calibrate (nếu tự làm lại):**
```
1. rolling_scores trên LUNA + NORMAL, fit_window=40, chi=None
2. SCORE_FLOOR = normal_max  (score 0)
3. SCORE_CEIL  = luna_p80    (score 100)
4. Verify: normal_max < luna_p80 (FP-safe)
```

**Sweep chi + fit_window để confirm optimal:**
```bash
python3 -m tools.cfi_mps_sweep   # chi=None, fit_window=40 thắng
```

---

## Phase 4 — Validation (Giờ 12-15)

```bash
# Fixed-threshold honest count — ĐÂY là bằng chứng cho judge
python3 -m tools.honest_detection_count
```

**Kỳ vọng output:**
```
Crisis detected @ RED (pre-cascade): 7/7
FP controls clean: normal = 0% RED
```

**QUAN TRỌNG:** dùng ngưỡng CỐ ĐỊNH (YELLOW=70/RED=90), KHÔNG dùng p80-per-scenario
(circular, ẢO). Xem 05_RESULTS.md để hiểu bẫy này.

---

## Phase 5 — Realtime pipeline (Giờ 15-18)

`emitter/orchestrator.py` — `RealtimeAlerter`:
```python
# History cần ~4500 blocks (40 return-windows × 100 stride + 300)
_CFI_MIN_HISTORY = (40 + 2) * 100 + 300  # ≈ 4500

def _cfi_mps_score_100(events):
    contracts = active_contracts(events, min_windows_active=3, window_blocks=300, stride_blocks=100)
    if len(contracts) < 2: return 0.0, {}
    R = build_returns_matrix(events, contracts, window_blocks=300, stride_blocks=100)
    if R.shape[1] < 40 + 1: return 0.0, {}
    window = R[:, -40:]  # most-recent 40 return-windows
    raw = mps_correlation_score(window)
    score = 100 * clamp((raw - 0.0061) / (0.0132 - 0.0061), 0, 1)
    rcs = rcs_scores(window, contracts) if score >= 50 else {}
    return round(score, 2), rcs
```

+ debounce (không fire mỗi block) + webhook emit. Full code trong `emitter/orchestrator.py`.

---

## Phase 6 — Demo + pitch (Giờ 18-24)

```bash
# Dashboard (nếu dùng demo/dashboard.py) → localhost:8080
python3 -m demo.dashboard
```

Xem `06_DEMO_PITCH.md` cho kịch bản 5 phút.

---

## Checklist "đủ để demo"

- [ ] `engine/cfi/` + `engine/mps/v2.py` — synthetic test pass
- [ ] ≥ 3 fixtures extracted (luna/ftx/normal đủ để show)
- [ ] `honest_detection_count` chạy ra ≥ 3/3 crisis + 0% FP normal
- [ ] 1 slide: "7/7 crisis, 0% FP, lead 10-66h"
- [ ] RCS demo: chỉ đúng tâm chấn (cUSDC/DAI-WETH cho LUNA)

---

## Bẫy đã gặp (đừng lặp lại)

1. **p80-per-scenario threshold = ẢO** — mọi scenario luôn có 20% window > p80 của nó.
   Dùng ngưỡng CỐ ĐỊNH.
2. **chi < 4 đảo signal** — bond-dim truncation quá mạnh làm mất mode. Dùng chi=None.
3. **multipleOf:0.01 trong JSON schema** — IEEE 754 làm 72.38 fail. Bỏ constraint.
4. **fit_window quá nhỏ (10-15)** — noise. fit_window=40 ổn định.
5. **Normalize features TRƯỚC entropy** — nếu dùng MPS v1 (graph). Với v2 (correlation)
   thì Ledoit-Wolf đã normalize sẵn.
6. **Build full stack TRƯỚC khi validate signal = SAI.** De-risk signal trên fixture
   NGAY khi có core algorithm. Đừng xây API/dashboard trước khi biết signal có work.
