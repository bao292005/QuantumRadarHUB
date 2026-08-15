---
stepsCompleted: [step-01-validate-prerequisites, step-02-design-epics, step-03-create-stories, step-04-final-validation]
inputDocuments:
  - docs/01_PRODUCT_BRIEF.md
  - docs/02_ALGORITHM_SPEC.md
  - docs/03_BUILD_GUIDE.md
  - docs/04_DATA_GUIDE.md
  - docs/05_RESULTS.md
  - docs/06_DEMO_PITCH.md
  - docs/07_CODE_MANIFEST.md
  - docs/08_BMAD_WORKFLOW.md
---

# HUB_Hackathon_quantum_radar - Epic Breakdown

## Overview

Tài liệu này phân rã yêu cầu của QuantumRadar (hệ cảnh báo sớm sụp đổ dây chuyền DeFi)
từ các tài liệu hackathon (`docs/01`–`08`) thành epics và stories triển khai được.
Nguồn thay cho PRD = `01_PRODUCT_BRIEF.md` + `05_RESULTS.md`; nguồn thay cho
Architecture = `02_ALGORITHM_SPEC.md` + `07_CODE_MANIFEST.md`.

**Gate bất biến (mọi story liên quan signal):** `python3 -m tools.honest_detection_count`
phải ra **7/7 crisis @ RED (pre-cascade) + 0% FP trên `normal`**.

## Requirements Inventory

### Functional Requirements

FR1: Tính ma trận tương quan Ledoit-Wolf shrinkage từ ma trận returns on-chain (input N×T → output N×N), clip [-1,1].
FR2: Tính fragility = 1 − normalized von Neumann entropy của eigenvalues ma trận tương quan (HIGH = tập trung = crisis).
FR3: Build activity matrix (Σ|amount0| mỗi contract mỗi window) và returns matrix (log-returns) từ list event, với window_blocks=300, stride_blocks=100.
FR4: Lọc `active_contracts` (contract xuất hiện ≥ min_windows_active windows) và loại hàng std≈0 trước khi tính score.
FR5: `mps_correlation_score(returns_window)` trả fragility [0,1]; `rolling_scores` chấm mọi rolling window (fit_window=40).
FR6: `rcs_scores` — leave-one-out per contract, chỉ ra protocol/pool là tâm chấn (RCS dương = khuếch đại systemic risk).
FR7: Map raw fragility → score_100 qua clamp((raw−FLOOR)/(CEIL−FLOOR),0,1); phát alert level RED ≥ 90, YELLOW ≥ 70.
FR8: Extract fixtures từ Etherscan V2 logs API cho 13-contract universe (9 Uniswap V3 + Aave V2/V3 + Spark + 4 Compound cToken), decode raw log → tick schema 11 field, xuất gzip CSV.
FR9: Chọn đúng Aave version theo era (block < 16,493,000 → V2, sau → V3) và compute topic0 Compound bằng keccak (không đoán).
FR10: `iter_csv_events` — đọc gzip CSV fixtures → list event dict theo tick schema.
FR11: Calibrate SCORE_FLOOR/CEIL trên luna/normal (FLOOR=normal_max, CEIL=luna_p80, verify normal_max < luna_p80).
FR12: Sweep chi × fit_window để xác nhận optimal (chi=None, fit_window=40 thắng).
FR13: `honest_detection_count` — chấm 12 fixtures bằng ngưỡng CỐ ĐỊNH (70/90), in bảng mean/%RED/lead-time, tổng 7/7 crisis + 0% FP normal.
FR14: `RealtimeAlerter` (orchestrator) — nhận stream event, giữ ~4500 block history, tính score_100 + RCS (khi score≥50), debounce (không fire mỗi block).
FR15: Async webhook fan-out tới subscribers khi vượt ngưỡng; format alert payload theo `fragility_alert.schema.json`.
FR16: FastAPI: POST /subscribe (đăng ký webhook), GET /score (điểm hiện tại), GET /history (rolling score history); subscriber registry persist JSON; score_store lưu lịch sử.
FR17: Dashboard trực quan (localhost:8080) — replay crisis, hiển thị score leo lên RED trước cascade + panel RCS.

### NonFunctional Requirements

NFR1: **Core algorithm bất biến** — `engine/cfi/correlation.py`, `engine/cfi/onchain.py`, `engine/mps/v2.py` COPY VERBATIM từ `02_ALGORITHM_SPEC.md`, TUYỆT ĐỐI không re-derive/"cải tiến" (bảo toàn 7/7).
NFR2: **Hằng số calibration LOCKED** — SCORE_FLOOR=0.0061, SCORE_CEIL=0.0132, FIT_WINDOW=40, CHI=None, WINDOW_BLOCKS=300, STRIDE_BLOCKS=100. Đề xuất đổi → TỪ CHỐI.
NFR3: Dùng ngưỡng CỐ ĐỊNH (YELLOW=70/RED=90), KHÔNG dùng p80-per-scenario (circular/ẢO).
NFR4: JSON schema alert KHÔNG dùng `multipleOf` (IEEE 754 làm 72.38 fail); tick schema đủ 11 field, 5 protocol enum.
NFR5: CPU-only, không GPU; correlation 13×13 tính < 10ms; realtime-capable, cần ~4500 block (~16h) warmup.
NFR6: Không phụ thuộc external API ngoài Etherscan (chỉ để lấy history); Etherscan free tier 3 req/s, max 1000 rows/call → chunk block range khi vượt.
NFR7: Smoke test bắt buộc: `mps_correlation_score(synchronized) > mps_correlation_score(uncorrelated)` — fail = sai công thức entropy.
NFR8: Bộ test đầy đủ (mục tiêu ~661 tests) cho core + onchain + mps + orchestrator (mock scorer).
NFR9: Ngôn ngữ giao tiếp/tài liệu: Vietnamese; code + comment: English (theo config bmm).

### Additional Requirements

- **Cấu trúc package (Architecture spine, theo dependency order):** `numpy, sklearn` → `engine/cfi/correlation.py` → `engine/cfi/onchain.py` + `engine/mps/v2.py` → `tools/*` (calibrate, sweep, validate, honest_detection_count) → `emitter/orchestrator.py` (+ payload, webhook, registry, score_store) → `emitter/api.py`, `demo/dashboard.py`.
- **Package skeleton cần tạo:** `engine/cfi/`, `engine/mps/`, `ingestion/`, `tools/`, `emitter/`, `demo/`, `tests/unit/`, `contracts/`, `fixtures/backtest/` (kèm `__init__.py` cho package).
- **Contracts (JSON schema):** `contracts/tick_data.schema.json` (11 field), `contracts/fragility_alert.schema.json` (không multipleOf).
- **Môi trường:** `.env` chứa `ETHERSCAN_API_KEY`; deps: numpy, scikit-learn, fastapi, uvicorn, requests, pyyaml, jsonschema, pytest, pytest-asyncio.
- **Ranh giới generate:** Vùng CẤM = core Tier 1 + hằng số (copy tay). Vùng CHO PHÉP = ingestion, tools, emitter, api, dashboard, tests (giao `bmad-build`).
- **Fixtures:** 12 file `fixtures/backtest/*.csv.gz` (~80MB) sinh bằng `tools/extract_fixtures --period all`; block range + cascade block per fixture trong `04_DATA_GUIDE.md`.

### UX Design Requirements

Không có UX design contract chính thức (không có UI phức tạp). Yêu cầu trực quan duy nhất
gói trong FR17 (dashboard demo) và kịch bản pitch `06_DEMO_PITCH.md`:
- UX-DR1: Dashboard replay 1 crisis (LUNA) cho thấy score leo qua ngưỡng RED TRƯỚC cascade block, kèm panel RCS liệt kê top contributors — phục vụ live demo 5 phút.

### FR Coverage Map

FR1: Epic 1 — Ledoit-Wolf shrinkage correlation
FR2: Epic 1 — eigenvalue entropy → fragility
FR3: Epic 1 — activity/returns matrix builder
FR4: Epic 1 — active_contracts + std filter
FR5: Epic 1 — mps_correlation_score + rolling_scores
FR6: Epic 1 — rcs_scores leave-one-out
FR7: Epic 1 — score_100 + alert level (RED/YELLOW)
FR8: Epic 2 — extract fixtures Etherscan 13-contract
FR9: Epic 2 — Aave era selection + Compound keccak topic0
FR10: Epic 2 — csv_loader iter_csv_events
FR11: Epic 2 — calibrate SCORE_FLOOR/CEIL
FR12: Epic 2 — sweep chi × fit_window
FR13: Epic 2 — honest_detection_count (gate 7/7)
FR14: Epic 3 — RealtimeAlerter orchestrator + debounce
FR15: Epic 3 — async webhook fan-out + alert payload
FR16: Epic 3 — FastAPI subscribe/score/history + registry + score_store
FR17: Epic 3 — dashboard visualization

## Epic List

### Epic 1: Fragility Detection Engine (lõi đã proven)
Từ list on-chain event, tính được fragility score [0–100] + alert level + RCS tâm chấn.
Trái tim sản phẩm, standalone, verify được bằng synthetic data (smoke test).
Core = COPY VERBATIM từ `02_ALGORITHM_SPEC.md`, không re-derive.
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR7

### Epic 2: Historical Proof & Validation (gate 7/7)
Extract 12 fixtures thật từ Etherscan, calibrate, và `honest_detection_count` ra
7/7 crisis @ RED (pre-cascade) + 0% FP trên `normal`. Đây là bằng chứng cho judge/risk team.
**FRs covered:** FR8, FR9, FR10, FR11, FR12, FR13

### Epic 3: Realtime Early-Warning Delivery (sản phẩm + demo)
Risk team nhận alert realtime qua webhook + dashboard replay crisis. Lời hứa sản phẩm.
Tier 4 — optional, có thể cắt nếu thiếu giờ demo.
**FRs covered:** FR14, FR15, FR16, FR17

## Epic 1: Fragility Detection Engine (lõi đã proven)

Từ list on-chain event, tính được fragility score [0–100] + alert level + RCS tâm chấn.
Core = COPY VERBATIM từ `02_ALGORITHM_SPEC.md` — TUYỆT ĐỐI không re-derive (NFR1, NFR2).

### Story 1.1: Correlation spectral metrics (copy verbatim)

As a risk engineer,
I want một module tính ma trận tương quan Ledoit-Wolf và entropy phổ,
So that tôi có nền tảng đo mức đồng bộ giữa các protocol.

**Acceptance Criteria:**

**Given** package `engine/cfi/` được scaffold với `__init__.py`
**When** copy verbatim `engine/cfi/correlation.py` từ `02_ALGORITHM_SPEC.md`
**Then** `shrinkage_correlation` nhận (N,T) trả (N,N), diag=1.0, clip [-1,1]
**And** `eigenvalue_entropy` trả giá trị ∈ [0,1]; `max_eigenvalue`/`average_strength`/`strong_edge_density` chạy đúng
**And** không có dòng nào bị sửa công thức so với spec (NFR1)

### Story 1.2: Activity/returns matrix builder (copy verbatim)

As a risk engineer,
I want dựng activity matrix và log-returns matrix từ list event on-chain,
So that tôi biến raw event thành input cho correlation.

**Acceptance Criteria:**

**Given** `engine/cfi/onchain.py` copy verbatim từ spec
**When** gọi `build_returns_matrix(events, contracts, window_blocks=300, stride_blocks=100)`
**Then** trả ma trận (N × T-1) log-returns; `build_activity_matrix` tổng |amount0| theo pool_address mỗi window
**And** `active_contracts(min_windows_active)` chỉ giữ contract xuất hiện đủ số window (FR4)
**And** events rỗng hoặc <2 window trả mảng rỗng không crash

### Story 1.3: MPS correlation score + RCS + smoke test

As a risk engineer,
I want fragility score và RCS leave-one-out từ returns window,
So that tôi đo được độ mong manh hệ thống và tâm chấn.

**Acceptance Criteria:**

**Given** `engine/mps/v2.py` copy verbatim từ spec
**When** chạy smoke test với synthetic data
**Then** `mps_correlation_score(synchronized) > mps_correlation_score(uncorrelated)` (NFR7)
**And** `rcs_scores` trả dict sorted giảm dần theo đóng góp; `rolling_scores(fit_window=40)` chấm mọi window
**And** input <2 hàng hoặc <2 cột trả 0.0 an toàn

### Story 1.4: Score→alert mapping + hằng số LOCKED

As a risk engineer,
I want map raw fragility → thang [0,100] và ra alert level,
So that output dùng được cho cảnh báo với ngưỡng nhất quán.

**Acceptance Criteria:**

**Given** module hằng số với SCORE_FLOOR=0.0061, SCORE_CEIL=0.0132, FIT_WINDOW=40, CHI=None, WINDOW_BLOCKS=300, STRIDE_BLOCKS=100
**When** gọi `score_100(raw)` và `alert_level(score)`
**Then** raw≤FLOOR→0, raw≥CEIL→100, ở giữa clamp tuyến tính; RED khi ≥90, YELLOW khi ≥70, còn lại None (FR7)
**And** hằng số khớp chính xác `02_ALGORITHM_SPEC.md` (NFR2)

## Epic 2: Historical Proof & Validation (gate 7/7)

Extract 12 fixtures thật, calibrate, và chứng minh 7/7 crisis + 0% FP bằng ngưỡng cố định.

### Story 2.1: Tick schema + CSV loader

As a data engineer,
I want schema chuẩn cho tick event và loader đọc gzip CSV,
So that mọi downstream dùng chung một định dạng event.

**Acceptance Criteria:**

**Given** `contracts/tick_data.schema.json` (11 field, 5 protocol enum) và `ingestion/csv_loader.py`
**When** gọi `iter_csv_events` trên một file `*.csv.gz`
**Then** trả list dict với đủ 11 field (block_number, block_timestamp, protocol, event_type, pool_address, token0, token1, amount0, amount1, tx_hash, log_index)
**And** mỗi event hợp lệ theo schema (FR10)

### Story 2.2: Etherscan fixture extractor

As a data engineer,
I want script fetch log từ Etherscan cho 13-contract universe và decode ra tick,
So that tôi tạo được fixtures lịch sử để validate.

**Acceptance Criteria:**

**Given** `.env` có ETHERSCAN_API_KEY và `tools/extract_fixtures.py`
**When** chạy cho một period
**Then** fetch đúng 13 address + topic0 trong `04_DATA_GUIDE.md`; decode swap/borrow/liquidation/compound đúng offset (FR8)
**And** chọn Aave V2 nếu block<16,493,000 else V3; topic0 Compound tính bằng keccak; chunk block range khi >1000 rows/call (FR9, NFR6)

### Story 2.3: Extract 12 fixtures + calibrate FLOOR/CEIL

As a data engineer,
I want extract toàn bộ fixtures và calibrate ngưỡng score,
So that detector có thang điểm chuẩn để đánh giá.

**Acceptance Criteria:**

**Given** extractor hoạt động (Story 2.2)
**When** chạy `extract_fixtures --period all` rồi `tools/cfi_mps_calibrate.py` trên luna/normal
**Then** sinh 12 file `fixtures/backtest/*.csv.gz`
**And** SCORE_FLOOR=normal_max, SCORE_CEIL=luna_p80, verify normal_max < luna_p80 (FP-safe) (FR11)

### Story 2.4: Sweep chi × fit_window

As a risk engineer,
I want quét tham số chi và fit_window,
So that xác nhận cấu hình tối ưu không bị đảo signal.

**Acceptance Criteria:**

**Given** `tools/cfi_mps_sweep.py`
**When** quét chi × fit_window trên luna/normal
**Then** chi=None, fit_window=40 cho gap tốt nhất + FP-safe (FR12)
**And** xác nhận chi<4 làm đảo/mất signal (không dùng)

### Story 2.5: Honest detection count — GATE 7/7

As a risk team lead,
I want một báo cáo detection trung thực với ngưỡng cố định,
So that tôi tin detector thật sự dự báo được khủng hoảng.

**Acceptance Criteria:**

**Given** `tools/honest_detection_count.py` dùng ngưỡng CỐ ĐỊNH 70/90 (NFR3)
**When** chạy trên 12 fixtures
**Then** crisis detected @ RED (pre-cascade) == 7/7
**And** false-positive rate trên `normal` == 0%
**And** in bảng mean/%RED/lead-time mỗi fixture; RCS chỉ đúng tâm chấn per crisis (FR13)

## Epic 3: Realtime Early-Warning Delivery (sản phẩm + demo)

Risk team nhận alert realtime qua webhook + dashboard replay crisis. Optional (Tier 4).

### Story 3.1: Alert payload + orchestrator debounce

As a protocol risk team,
I want engine chấm điểm realtime và ra alert có debounce,
So that tôi nhận cảnh báo sớm mà không bị spam mỗi block.

**Acceptance Criteria:**

**Given** `emitter/payload.py`, `contracts/fragility_alert.schema.json`, `emitter/orchestrator.py`
**When** `RealtimeAlerter` nhận stream event với ≥4500 block history
**Then** tính score_100 + RCS (khi score≥50); alert payload hợp `fragility_alert.schema.json` (KHÔNG multipleOf, NFR4)
**And** debounce không fire mỗi block; <4500 block trả score 0 (warmup) (FR14, NFR5)

### Story 3.2: Webhook fan-out + subscriber registry

As a protocol risk team,
I want đăng ký webhook và nhận alert async,
So that hệ thống của tôi được thông báo tự động khi có rủi ro.

**Acceptance Criteria:**

**Given** `emitter/webhook.py` và `emitter/registry.py`
**When** một alert vượt ngưỡng được phát
**Then** fan-out async tới mọi subscriber đã đăng ký (FR15)
**And** registry persist subscriber ra JSON và load lại được sau restart

### Story 3.3: FastAPI endpoints + score store

As a protocol risk team,
I want API để subscribe và truy vấn score/history,
So that tôi tích hợp QuantumRadar vào hệ thống của mình.

**Acceptance Criteria:**

**Given** `emitter/api.py` và `emitter/score_store.py`
**When** gọi các endpoint
**Then** POST /subscribe đăng ký webhook; GET /score trả điểm hiện tại; GET /history trả rolling score history (FR16)
**And** score_store lưu lịch sử điểm theo thời gian

### Story 3.4: Dashboard demo

As a người thuyết trình,
I want dashboard replay một crisis trực quan,
So that judge thấy score leo lên RED trước cascade và biết tâm chấn.

**Acceptance Criteria:**

**Given** `demo/dashboard.py` chạy tại localhost:8080
**When** replay fixture LUNA
**Then** hiển thị score leo qua ngưỡng RED TRƯỚC cascade block, kèm panel RCS top contributors (FR17, UX-DR1)
**And** chạy được CPU-only, không cần GPU
