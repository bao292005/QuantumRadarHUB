# 🛰️ QuantumRadar

> **Hệ cảnh báo sớm sụp đổ dây chuyền (systemic risk) trên DeFi** — phát hiện khủng hoảng
> *trước* khi cascade xảy ra, bằng cấu trúc tương quan on-chain thay vì chờ giá rơi.

Thuật toán lõi: **CFI** (Correlation Fragility Index) + **MPS** (Matrix Product State) +
**RCS** (Risk Contribution Score) chạy trên dữ liệu on-chain thật (Uniswap / Aave / Compound).

**Ý tưởng một dòng:** *Khủng hoảng = mọi giao thức đồng loạt biến động cùng nhịp.* CFI đo mức
đồng bộ của ma trận tương quan; khi phổ eigenvalue "tập trung" → hệ dễ sụp dây chuyền. MPS đo
entropy phổ; RCS chỉ ra giao thức nào là **tâm chấn**.

---

## ✅ Kết quả (trung thực)

- **7/7 sự kiện khủng hoảng** phát tín hiệu RED **trước** cascade (LUNA, FTX, stETH depeg,
  May-2021, WBTC cascade, ETH cascade FTX-week, USDC/SVB depeg).
- **0 false positive** trên fixture thị trường bình thường (`normal_2023_03_15`).
- RCS chỉ đúng pool/protocol bị stress nhất trong từng crisis.

> **Caveat quan trọng (đọc `docs/09` + `docs/12`):** con số 7/7 là trên các *fixture khủng hoảng*.
> Trên *span liên tục nhiều năm*, ngưỡng cố định hiện tại báo giả cao — bước tiếp theo (đã ghi
> trong doc) là ngưỡng **tương đối/analog** tự-calibrate. Chúng tôi công bố cả điểm mạnh lẫn giới hạn.

---

## 🏗️ Kiến trúc

```
On-chain events (Etherscan logs)
        │
        ▼
engine/  ─ CFI + MPS + RCS  ──►  score 0–100 + alert (RED≥90 / YELLOW≥70) + RCS epicenter
        │
        ├──► emitter/  FastAPI  (:8000)  ── /api/v1/... ──►  Next.js dashboard + Chrome extension
        └──► demo/     dashboard (:8080)  ── backtest nến + oscillator + heatmap tương quan
```

---

## ⚡ Chạy nhanh (clone → chạy trong ~3 phút)

**Yêu cầu:** Python 3.11+ (test trên 3.12) · Node 18+ (test trên 22). Không cần GPU. Không cần API key để xem demo.

### 1) Clone
```bash
git clone <repo-url> && cd HUB_Hackathon_quantum_radar
cp .env.example .env          # không bắt buộc sửa gì để chạy demo
```

### 2) Backend API — cửa sổ terminal #1
```bash
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn emitter.api:app --port 8000
```
→ API + Swagger docs: **http://127.0.0.1:8000/docs**

### 3) Frontend (dashboard + extension UI) — cửa sổ terminal #2
```bash
npm install
npm run dev
```
→ Mở **http://localhost:3000** — thấy biểu đồ nến backtest + extension sidebar (nối thẳng backend :8000).

### 4) (Tuỳ chọn) Dashboard backtest standalone
```bash
python3 -m demo.dashboard          # → http://localhost:8080
```

Xong. Nến, oscillator fragility, heatmap tương quan 13×13, RCS tâm chấn — tất cả từ thuật toán thật.

---

## 🔎 Kiểm chứng nhanh

```bash
pytest -q                # bộ test Python (unit)
npx tsc --noEmit         # type-check frontend (EXIT 0 = sạch)
python3 -m tools.honest_detection_count      # in lại gate 7/7
```

---

## 📁 Cấu trúc dự án

```
engine/            Lõi thuật toán (KHOÁ — giữ nguyên để tái lập 7/7)
  ├─ cfi/          Correlation Fragility Index (Ledoit-Wolf, PCA-CFI, data cleaning)
  ├─ mps/          Matrix Product State (v2 detector, generative, scenario, price_paths)
  └─ scoring.py    score_100 + hằng số calibration KHOÁ (SCORE_FLOOR/CEIL)
ingestion/         csv_loader — nạp tick-data đã extract
emitter/           FastAPI realtime: api.py, orchestrator, replay, extension_state
demo/              dashboard.py — backtest (:8080) + build_timeline / forecast / corr
tools/             extract_fixtures, f1_backtest, honest_detection_count, price, baselines…
fixtures/backtest/ Dữ liệu on-chain (fixture khủng hoảng nhỏ đi kèm; span lớn tự tạo lại)
app/               Next.js App Router (/, /demo, /backtest)
components/        React — demo/CandlestickBacktest, extension/*
lib/               api.ts (client) · types.ts · mock-data.ts
public/            manifest.json (Chrome extension)
tests/             pytest
docs/              01–12: spec, results, honest findings, UI/UX (đọc 02, 05, 11, 12)
```

---

## 🔑 Biến môi trường (`.env`)

Copy `.env.example` → `.env`. **Chỉ cần key khi extract fixtures mới** — demo chạy không cần gì.

| Biến | Bắt buộc | Dùng cho |
|---|---|---|
| `ETHERSCAN_API_KEY` | chỉ khi extract | Tạo fixtures mới từ on-chain (free tier đủ) |
| `NEXT_PUBLIC_QUANTUMRADAR_API_URL` | không | URL backend cho frontend (mặc định `http://127.0.0.1:8000`) |
| `WSS_URL` / `ALCHEMY_KEY` / … | không | Realtime WSS ingestion (không cần cho backtest/demo) |

---

## 🗂️ Fixtures (dữ liệu backtest)

- **Fixture khủng hoảng nhỏ** (LUNA, FTX, stETH, USDC…) **đi kèm repo** → chạy backtest ngay.
- **Span lớn** (`seg1/seg2/cont_q2`, hàng trăm MB) **không kèm** (vượt giới hạn GitHub) — tạo lại khi cần:

```bash
# cần ETHERSCAN_API_KEY trong .env
python3 -m tools.extract_fixtures --period luna_2022_05_09        # 1 crisis
python3 -m tools.extract_fixtures --from-block 15010000 --to-block 17600000 --name seg1_2022_2023
```

---

## 🧩 Chrome extension (tuỳ chọn)

```bash
npm run build            # build Next.js + đóng gói extension
```
Vào `chrome://extensions` → bật Developer mode → **Load unpacked** → chọn thư mục `out/` (hoặc `public/`).
Extension mặc định nối `http://127.0.0.1:8000`; đổi API khác qua `NEXT_PUBLIC_QUANTUMRADAR_API_URL` +
thêm domain vào `host_permissions` trong `public/manifest.json`.

---

## 📚 Đọc thêm

| Doc | Nội dung |
|---|---|
| `docs/02_ALGORITHM_SPEC.md` | Toán CFI+MPS+RCS đầy đủ |
| `docs/05_RESULTS.md` | Validation 7/7 + caveat |
| `docs/09_F1_HONEST_FINDINGS.md` | Phân tích F1 trung thực (vì sao B0 thắng trên volume) |
| `docs/11_ALGORITHM_COMPLETE.md` | Thuật toán hoàn chỉnh hiện tại |
| `docs/12_UI_CRISIS_UX.md` | Thiết kế UI hiển thị khủng hoảng + hướng analog |

---

## 🛠️ Tech stack

Python 3.11+ · numpy · scikit-learn (Ledoit-Wolf) · FastAPI · uvicorn — CPU-only (ma trận N≈13).
Next.js 15 · React 19 · TypeScript · Canvas. Data: Etherscan V2 logs API. Test: pytest.
