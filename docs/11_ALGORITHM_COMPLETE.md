# Thuật toán hoàn chỉnh — QuantumRadar (bản hiện tại)

Hợp nhất `02_ALGORITHM_SPEC.md` (lõi) + `10_ALGORITHM_UPGRADES.md` (nâng cấp) thành **một
bản mô tả thuật toán đầy đủ, honest**. Lõi giữ nguyên (LOCKED, bảo toàn 7/7); các nâng cấp
là lớp bổ sung, ghi rõ **đã wired hay chỉ nghiên cứu**.

> Code verbatim của lõi: xem `02_ALGORITHM_SPEC.md`. Kết quả đo + tradeoff: `05`, `09`, `10`.

---

## 0. Kiến trúc tổng thể

```
on-chain events
   ↓ engine/cfi/onchain.py          activity → log-returns
   ↓ engine/cfi/clean.py     [Tier1] MAD + winsorize (giảm spike giả)
   ↓ engine/cfi/correlation.py       Ledoit-Wolf correlation
   ├─ engine/mps/v2.py       [LÕI]   entropy → fragility → score_100
   └─ engine/cfi/indicator.py [Tier1] PCA-CFI 4 metric (nghiên cứu)
   ↓ engine/scoring.py               score_100 + alert_level (hằng số LOCKED)
   ↓ emitter/orchestrator.py [Tier1] persistence(N=4) + hysteresis  → ALERT + RCS
song song:
   engine/mps/generative.py [Tier2]  OOD precision-filter (demo)  +  scenario forecast (wired UI)
```

---

## 1. LÕI phát hiện — CFI+MPS  🔒 LOCKED

**Trực giác:** khủng hoảng = mọi protocol biến động ĐỒNG BỘ → ma trận tương quan tập trung
1 mode → entropy phổ THẤP → fragility CAO.

1. `shrinkage_correlation` — Ledoit-Wolf, (N×T)→(N×N)
2. `eigenvalue_entropy` — H = −1/lnN · Σ p_k ln p_k ∈ [0,1], THẤP = mong manh
3. `mps_correlation_score` = **1 − entropy** (HIGH = crisis)
4. `score_100` = clamp((raw−FLOOR)/(CEIL−FLOOR), 0, 1)·100; `alert_level` RED≥90 / YELLOW≥70
5. `rcs_scores` — leave-one-out: protocol nào khuếch đại systemic risk (tâm chấn)

**Kết quả (bằng chứng lõi):** 7/7 crisis pre-cascade @ RED, 0% FP trên `normal`, lead 10–66h.

**Hằng số LOCKED** (`engine/scoring.py`):
```
SCORE_FLOOR=0.0061  SCORE_CEIL=0.0132  FIT_WINDOW=40  CHI=None
WINDOW_BLOCKS=300   STRIDE_BLOCKS=100
```

---

## 2. Data cleaning  🟢 Tier-1 (tuỳ chọn)

`engine/cfi/clean.py` — theo arXiv:2601.08540 §II: **winsorize 0.5% + MAD-clip (k=12)** trên
returns trước correlation → loại spike kỹ thuật / thin-pool tạo tương quan giả (nguồn báo giả).

---

## 3. PCA-CFI 4 metric  🔬 Tier-1 (nghiên cứu, KHÔNG thay lõi)

`engine/cfi/indicator.py` — CFI thật của bài gốc: hợp nhất **4 metric** (avg_strength, max_eig,
strong_edge_density, entropy) bằng **PCA (PC1)**. Loadings đo được `[+.52,+.53,+.42,−.53]` khớp
bài gốc. Cắt FP mạnh (busd 23→0%) **nhưng mất recall (7/7→5/7, mất LUNA)** → giữ làm **tín hiệu
phụ**, không thay entropy LOCKED.

---

## 4. Persistence + Hysteresis  ✅ Tier-1 (ĐÃ WIRED)

`emitter/orchestrator.py` — logic ALERT thực tế đã deploy:
- **Persistence:** chỉ bật alert sau **N=4 cửa sổ RED liên tiếp** (lọc spike lẻ)
- **Hysteresis:** đã bật thì giữ tới khi score < 70 (hết nhấp nháy)

**Hiệu quả:** giữ **7/7 (cả LUNA)** + giảm ~36% báo spam spiky (busd 11→7 episodes). Không đụng
lõi (chỉ hậu xử lý điểm số). Đổi lại: lead co nhẹ trên event spiky (LUNA 9.4→~3h).

---

## 5. MPS generative — 2 vai trò  🟡/✅ Tier-2

MPS-Born density / tensor-train (arXiv:2402.17148). Phân biệt với "MPS lõi" (entropy detector):
đây là **MPS SINH**.

### 5a. Precision-filter (OOD)  🟡 mechanism (chưa wired)
`engine/mps/generative.py` — học phân phối "normal", cửa sổ **likelihood thấp = OOD = bất thường**.
Gate: entropy RED **AND** OOD. Demo (P90): **giữ 7/7 + busd 23→5%, euler 13→7%** — tốt nhất trong
các hướng giảm FP mà giữ LUNA. **Chưa wired** vì train còn nhiễm (cont_q2_2022 chứa luna/stETH) →
cần re-fit trên dải calm sạch (seg1-3).

### 5b. Scenario forecaster  ✅ ĐÃ WIRED (trang "Kịch bản")
`engine/mps/scenario.py` — mô hình **tensor-train transition** của động lực điểm số. Sample forward
paths → xác suất **liquidity / recovery / contagion** THẬT (thay hardcode). Context-sensitive:
lúc RED, contagion 12→24%. Nối vào `emitter/api.py` → `ScenarioForecastPage`.
> Chỉ `probability` là thật; impact/timeframe/actions vẫn minh hoạ.

---

## 6. Kết quả đo (honest)

| Thước đo | Kết quả | Ghi chú |
|---|---|---|
| Event-level 7/7 | ✅ 7/7 pre-cascade, 0% FP normal | ngưỡng cố định |
| Thuật toán mới (entropy+persistence[+MPS filter]) | **7/7 giữ, FP↓ khắp bảng** | lead co nhẹ |
| Scorecard công bằng (cùng budget) | **CFI 6/6 OOS vs B0 2/6** | `event_scorecard` |
| F1 continuous (volume) | CFI 0.077 vs B0 0.445 | **sai sân** — xem `09` |
| MCC (volume label) | CFI −0.12, B0 +0.35 | volume là sân B0 |

**Đúng sân của CFI:** phát hiện cascade HỆ THỐNG (đồng bộ, có tích tụ) sớm — LUNA/stETH/depeg-class.
**Sai sân:** dự báo volume thanh lý (B0 thắng — đúng thiết kế).

---

## 7. Ranh giới trung thực

- **Tail detector hiếm**, KHÔNG phải volume/price forecaster.
- **Không** off-chain fraud thuần (FTX-fraud) — chỉ bắt **ETH cascade on-chain đi kèm**.
- **Không** exploit (Euler = 1-block, không tích tụ → không dự báo được).
- Số MPS (filter + scenario) cần **calm data sạch** (seg1-3) để chốt out-of-sample.
- Mẫu nhỏ (7 event) → power thống kê hạn chế; là **1 tín hiệu** có người review.

---

## 8. Trạng thái từng phần

| Thành phần | File | Trạng thái |
|---|---|---|
| CFI+MPS core | `engine/{cfi,mps/v2,scoring}` | 🔒 LOCKED |
| Data cleaning | `engine/cfi/clean.py` | 🟢 tuỳ chọn |
| PCA-CFI | `engine/cfi/indicator.py` | 🔬 nghiên cứu |
| Persistence/hysteresis | `emitter/orchestrator.py` | ✅ wired |
| MPS OOD filter | `engine/mps/generative.py` | 🟡 demo (chờ calm data) |
| MPS scenario | `engine/mps/scenario.py` | ✅ wired (UI) |

---

## 9. Tái lập

```bash
python3 -m tools.honest_detection_count   # 7/7 + 0% FP (lõi)
python3 -m tools.entropy_persist_eval     # persistence (đã wired)
python3 -m tools.cfi_pca_eval             # PCA-CFI (nghiên cứu)
python3 -m tools.mps_filter_eval          # MPS OOD filter (demo)
python3 -m tools.event_scorecard          # scorecard công bằng vs B0
python3 -m tools.f1_backtest --span cont_q2_2022   # F1 volume (sai sân, honest)
python3 -m pytest tests/unit -q           # 62 tests
```
