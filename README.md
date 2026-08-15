# QuantumRadar — Hackathon Rebuild Package

**Mục tiêu:** Xây dựng lại toàn bộ sản phẩm thuật toán trong 24h cho hackathon.

QuantumRadar = **hệ cảnh báo sớm sụp đổ dây chuyền DeFi**, phát hiện systemic risk
bằng **CFI (Correlation Fragility Index) + MPS (Matrix Product State) + RCS (Risk
Contribution Score)** trên dữ liệu on-chain realtime.

---

## Kết quả đã đạt (bằng chứng)

- **7/7 sự kiện khủng hoảng** dự báo được TRƯỚC cascade (lead 10–66h)
- **0% false positive** trên thị trường bình thường
- RCS chỉ đúng protocol/pool bị stress nhất trong mỗi crisis
- 537 LOC core algorithm, 12 fixtures thật từ mainnet, 661 tests pass

| Sự kiện | Lead time | Detect |
|---------|-----------|--------|
| LUNA (2022-05) | ~10h | ✅ |
| FTX (2022-11) | ~37h | ✅ |
| stETH depeg (2022-06) | ~66h | ✅ |
| May 2021 crash | ~48h | ✅ |
| WBTC cascade (2022-06) | ~48h | ✅ |
| ETH cascade FTX-week | ~49h | ✅ |
| USDC depeg/SVB (2023-03) | ~28h | ✅ |
| **Normal market** | — | **0% FP** ✅ |

---

## Đọc theo thứ tự

| File | Nội dung | Cho ai |
|------|----------|--------|
| `01_PRODUCT_BRIEF.md` | Problem, solution, positioning, market | PM / pitch |
| `02_ALGORITHM_SPEC.md` | Toán CFI+MPS+RCS + code đầy đủ | Dev / kỹ thuật |
| `03_BUILD_GUIDE.md` | **Công thức build 24h step-by-step** | Dev thực thi |
| `04_DATA_GUIDE.md` | Fixtures + extraction từ Etherscan | Dev data |
| `05_RESULTS.md` | Validation trung thực (7/7, caveat) | Judge / demo |
| `06_DEMO_PITCH.md` | Kịch bản demo + pitch 5 phút | Presenter |
| `07_CODE_MANIFEST.md` | Map file nguồn theo tier + minimal rebuild | Dev |
| `08_BMAD_WORKFLOW.md` | Dùng BMad rebuild 24h (copy-verbatim vs generate) | Dev / BMad |
| `requirements.txt` | Deps pinned theo tier | Setup |
| `setup.sh` | One-command setup + smoke test | Setup |

---

## Timeline 24h (đề xuất)

```
Giờ 0-2:   Setup env + đọc 02_ALGORITHM_SPEC + 03_BUILD_GUIDE
Giờ 2-6:   Build core: engine/cfi/ + engine/mps/v2.py (copy + test)
Giờ 6-10:  Extract fixtures (Etherscan API) — chạy background
Giờ 10-14: Pipeline: ingestion → orchestrator → calibrate
Giờ 14-18: Validation + honest_detection_count → có bằng chứng 7/7
Giờ 18-21: Demo dashboard + pitch prep
Giờ 21-24: Polish + rehearse demo
```

---

## Tech stack

- **Python 3.11+**, numpy, scikit-learn (Ledoit-Wolf), FastAPI
- KHÔNG cần GPU (CFI+MPS chạy CPU, correlation matrix nhỏ N≈13)
- Data: Etherscan V2 logs API (free tier đủ)
- Test: pytest

---

## Core insight (nếu chỉ đọc 1 dòng)

> **Crisis = mọi protocol đồng loạt biến động cùng chiều.**
> CFI đo mức độ đồng bộ (correlation) của activity giữa các protocol.
> Khi correlation matrix "tập trung" (1 eigenvalue lớn chiếm hết) → hệ dễ sụp dây chuyền.
> MPS đo entropy của phổ eigenvalue; RCS chỉ ra protocol nào là tâm chấn.
