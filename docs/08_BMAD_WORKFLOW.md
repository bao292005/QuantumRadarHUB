# BMad Workflow — 24h Hybrid Plan

Cách dùng BMad Method để rebuild QuantumRadar trong 24h, **giữ nguyên kết quả 7/7**.

**Nguyên tắc vàng:**
> Thuật toán = spec CỐ ĐỊNH (copy verbatim). Scaffolding = cho agent generate.
> Gate mọi story = `honest_detection_count` ra 7/7 + 0% FP.

---

## Vùng CẤM generate (COPY VERBATIM)

Các file này đã proven — BMad/agent **TUYỆT ĐỐI KHÔNG được re-derive hay "cải tiến"**:

```
engine/cfi/correlation.py     ← eigenvalue entropy formula
engine/cfi/onchain.py         ← activity/returns matrix
engine/mps/v2.py              ← mps_correlation_score + RCS
```

Và các hằng số calibration (LOCKED):
```
SCORE_FLOOR=0.0061  SCORE_CEIL=0.0132  FIT_WINDOW=40  chi=None
WINDOW_BLOCKS=300   STRIDE_BLOCKS=100
```

Nguồn copy: `02_ALGORITHM_SPEC.md` (có full code). Nếu agent đề xuất đổi công thức
entropy / normalize / fit_window → **TỪ CHỐI**. Xem bẫy trong `03_BUILD_GUIDE.md`.

---

## Vùng CHO PHÉP generate

```
ingestion/csv_loader.py       ← đọc gzip CSV (straightforward)
tools/extract_fixtures.py     ← Etherscan fetch (dùng addresses/topics từ 04)
tools/*_calibrate.py, validate ← harness quanh core cố định
emitter/orchestrator.py       ← wiring score→debounce→webhook
emitter/api.py, webhook.py    ← FastAPI + async
demo/dashboard.py             ← visualization
tests/*                       ← test scaffolding
```

---

## Config BMad hiện có

```
_bmad/bmm/config.yaml: user=bao, comm=Vietnamese, docs=English, skill=intermediate
Stories: _bmad-output/implementation-artifacts/<key>.md
Board:   _bmad-output/sprint-status.yaml
```

---

## Timeline 24h với BMad skills

### Phase A — Planning (Giờ 0-2)

| Bước | BMad skill | Input | Output |
|------|-----------|-------|--------|
| A1 | `bmad-product-brief` | `01_PRODUCT_BRIEF.md` | Brief (đã gần xong, chỉ review) |
| A2 | `bmad-prd` | Brief + `05_RESULTS.md` (acceptance) | PRD với success = 7/7 |
| A3 | `bmad-architecture` | `07_CODE_MANIFEST.md` | Arch spine (tier structure) |
| A4 | `bmad-create-epics-and-stories` | `03_BUILD_GUIDE.md` phases | Epics + stories |

**Shortcut:** brief + arch gần như copy từ hackathon docs → đừng để agent viết lại từ 0.

### Phase B — Core algorithm (Giờ 2-5) — KHÔNG DÙNG BMAD DEV

```
COPY VERBATIM từ 02_ALGORITHM_SPEC.md:
  engine/cfi/correlation.py, onchain.py, engine/mps/v2.py
Chạy smoke test:
  synchronized > uncorrelated  (setup.sh làm sẵn)
```
→ Đây là bước KHÔNG giao cho agent. Copy tay, test tay.

### Phase C — Data (Giờ 5-9, background)

| Bước | BMad skill | Note |
|------|-----------|------|
| C1 | `bmad-dev-story` (data story) | Generate `csv_loader.py` + `extract_fixtures.py` từ addresses/topics trong `04_DATA_GUIDE.md` |
| C2 | chạy extract | `python3 -m tools.extract_fixtures --period all` (background) |

**Contract:** agent PHẢI dùng đúng 13 addresses + topic0 trong `04`. Đừng để đoán.

### Phase D — Validation (Giờ 9-12) — GATE

| Bước | BMad skill | Gate |
|------|-----------|------|
| D1 | `bmad-dev-story` | Generate `honest_detection_count.py` (logic trong `03/05`) |
| D2 | chạy | `python3 -m tools.honest_detection_count` |
| D3 | `bmad-check-implementation-readiness` | **PHẢI ra 7/7 + 0% FP normal** |

→ Nếu D2 không ra 7/7: KHÔNG phải lỗi harness — kiểm tra core có bị agent sửa không.

### Phase E — Realtime + demo (Giờ 12-18)

| Bước | BMad skill | Output |
|------|-----------|--------|
| E1 | `bmad-quick-dev` | `emitter/orchestrator.py` (wiring) |
| E2 | `bmad-quick-dev` | `emitter/api.py` + `webhook.py` |
| E3 | `bmad-quick-dev` | `demo/dashboard.py` |
| E4 | `bmad-code-review` | Review scaffolding (KHÔNG review core cố định) |

### Phase F — Polish + pitch (Giờ 18-24)

| Bước | BMad skill | Output |
|------|-----------|--------|
| F1 | `bmad-sprint-status` | Trạng thái tổng |
| F2 | manual | Rehearse `06_DEMO_PITCH.md` |
| F3 | `bmad-retrospective` | (nếu còn thời gian) |

---

## Acceptance criteria mẫu (dán vào mọi story)

```
GIVEN core algorithm copied verbatim from 02_ALGORITHM_SPEC.md
WHEN  python3 -m tools.honest_detection_count runs on 12 fixtures
THEN  crisis detected @ RED (pre-cascade) == 7/7
AND   normal market false-positive rate == 0%
AND   RCS identifies plausible top contributors per crisis
```

Story chưa đạt gate này = **chưa done**, dù code compile + test pass.

---

## Anti-patterns (đừng làm)

1. ❌ Để `bmad-dev-story` "implement CFI from scratch" → sẽ ra công thức khác, vỡ 7/7
2. ❌ Cho agent "optimize" fit_window / chi / calibration → các giá trị đã sweep tối ưu
3. ❌ Full BMad ceremony cho core (brief→PRD→arch→story cho 1 hàm entropy) → phí giờ
4. ❌ Dùng số 6/6 (p80 ẢO) làm gate → phải là 7/7 fixed-threshold
5. ❌ Review/refactor core algorithm bằng `bmad-code-review` → nó proven rồi, để yên

---

## Nếu chỉ có 6h (BMad minimal)

```
1. Copy Tier 1 verbatim (không BMad)              [1h]
2. bmad-quick-dev: csv_loader + extract_fixtures   [1h]
3. Extract 3 fixtures (luna/ftx/normal)            [1h, background]
4. bmad-quick-dev: honest_detection_count          [1h]
5. Chạy gate → 3/3 crisis + 0% FP                  [30m]
6. Pitch prep (06_DEMO_PITCH.md)                   [1.5h]
```

= Đủ demo thuật toán + bằng chứng, bỏ realtime/API.

---

## Tóm tắt 1 dòng

> Dùng BMad cho **scaffolding** (data, API, tests, demo), COPY VERBATIM cho **core**
> (cfi/mps/calibration), và để `honest_detection_count == 7/7` làm **gate bất biến**.
