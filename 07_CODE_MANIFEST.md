# Code Manifest — File cần thiết

Danh sách chính xác file nguồn để rebuild. Copy theo thứ tự dependency.

---

## Tier 1 — Core algorithm (BẮT BUỘC, 537 LOC)

| File | LOC | Vai trò | Dependency |
|------|-----|---------|------------|
| `engine/cfi/__init__.py` | 0 | package marker | — |
| `engine/cfi/correlation.py` | 106 | Ledoit-Wolf corr + spectral metrics | numpy, sklearn |
| `engine/cfi/onchain.py` | 144 | activity/returns matrix từ events | numpy |
| `engine/mps/__init__.py` | 0 | package marker | — |
| `engine/mps/v2.py` | 180 | mps_correlation_score + rcs_scores | numpy, cfi.correlation |
| `engine/cfi/indicator.py` | 107 | CFIModel (PCA fusion, optional) | numpy, cfi.correlation |

**Đây là trái tim sản phẩm. Có Tier 1 = có thuật toán.**

---

## Tier 2 — Data pipeline (BẮT BUỘC để có fixtures)

| File | Vai trò |
|------|---------|
| `tools/extract_fixtures.py` | Fetch Etherscan → gzip CSV (13 contract, 12 period) |
| `ingestion/csv_loader.py` | Đọc gzip CSV → list of event dicts (`iter_csv_events`) |

---

## Tier 3 — Validation (BẮT BUỘC để có bằng chứng)

| File | Vai trò |
|------|---------|
| `tools/cfi_mps_calibrate.py` | Calibrate SCORE_FLOOR/CEIL trên luna/ftx/normal |
| `tools/cfi_mps_sweep.py` | Sweep chi × fit_window → tìm optimal |
| `tools/validate_10_scenarios.py` | Chạy 12 scenario |
| `tools/honest_detection_count.py` | **Fixed-threshold honest count (bằng chứng 7/7)** |

---

## Tier 4 — Realtime + alert (cho demo live, optional)

| File | Vai trò |
|------|---------|
| `emitter/orchestrator.py` | RealtimeAlerter — score + debounce + emit |
| `emitter/payload.py` | format_alert + alert_level (RED/YELLOW) |
| `emitter/webhook.py` | async webhook fan-out |
| `emitter/registry.py` | subscriber registry (JSON persist) |
| `emitter/api.py` | FastAPI: POST /subscribe, GET /score |
| `emitter/score_store.py` | rolling score history + GET /history |
| `demo/dashboard.py` | Visual dashboard localhost:8080 |

---

## Tier 5 — Tests (khuyến nghị, 661 tests)

| File | Tests |
|------|-------|
| `tests/unit/test_cfi_correlation.py` | spectral metrics |
| `tests/unit/test_cfi_onchain.py` | returns matrix builder (13) |
| `tests/unit/test_mps_v2.py` | mps_correlation_score + RCS (18) |
| `tests/unit/test_cfi_indicator.py` | CFIModel |
| `tests/unit/test_orchestrator.py` | debounce/emit (mock scorer, 8) |

---

## Contracts (JSON schemas)

| File | Vai trò |
|------|---------|
| `contracts/tick_data.schema.json` | Event schema (11 field, 5 protocol enum) |
| `contracts/fragility_alert.schema.json` | Alert payload (KHÔNG có multipleOf) |

---

## Fixtures (data, 12 files ~80MB total)

```
fixtures/backtest/
  luna_2022_05_09.csv.gz          steth_depeg_2022_06.csv.gz
  ftx_2022_11_08.csv.gz           may_2021_eth_crash.csv.gz
  normal_2023_03_15.csv.gz        wbtc_cascade_2022_06.csv.gz
  eth_cascade_ftx_week_2022_11.csv.gz   usdc_depeg_2023_03.csv.gz
  busd_freeze_2023_02.csv.gz      crv_near_miss_2023_08.csv.gz
  crv_near_miss_2023_11.csv.gz    euler_hack_2023_03.csv.gz
```
Extract bằng: `python3 -m tools.extract_fixtures --period all`

---

## Dependency graph (import order)

```
numpy, sklearn
    ↓
engine/cfi/correlation.py
    ↓
engine/cfi/onchain.py ←──┐
engine/mps/v2.py ────────┤
    ↓                    │
tools/*.py (calibrate, validate)
    ↓
emitter/orchestrator.py ─┘  (+ payload, webhook, registry)
    ↓
emitter/api.py, demo/dashboard.py
```

---

## Minimal viable rebuild (nếu chỉ có 6h)

Chỉ cần:
1. `engine/cfi/correlation.py` + `engine/cfi/onchain.py` + `engine/mps/v2.py` (Tier 1)
2. `ingestion/csv_loader.py` (đọc data)
3. `tools/extract_fixtures.py` → extract 3 fixtures (luna/ftx/normal)
4. `tools/honest_detection_count.py` → chứng minh 3/3

= Đủ để demo thuật toán + bằng chứng. Bỏ qua Tier 4 (realtime/API) nếu thiếu thời gian.

---

## Related docs đã có sẵn trong repo (tham khảo)

| Doc | Nội dung |
|-----|----------|
| `research/all_crisis_candidates.md` | 10 sự kiện + block ranges |
| `research/cfi_validation.md` | CFI validation history (honest) |
| `research/literature_review.md` | Prior art (arXiv sources) |
| `calibration/validation_10_scenarios.md` | Kết quả validation |
| `docs/product_direction.md` | Positioning lịch sử |
