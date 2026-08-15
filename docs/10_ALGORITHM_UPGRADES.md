# Algorithm Upgrades — Tier 1 (PCA-CFI + Data Cleaning + Persistence)

Ghi lại các nâng cấp thuật toán sau khi tham khảo tài liệu trong `doc-ref/`, kèm **kết
quả đo trung thực** (cả mặt được lẫn mặt mất). Nguyên tắc: **không đụng core LOCKED**
(entropy detector giữ nguyên để bảo toàn 7/7), mọi nâng cấp là **song song + đo A/B**.

Nguồn tham khảo:
- **arXiv:2601.08540** — "Systemic Risk in DeFi: Network-Based Fragility of TVL" (CFI gốc)
- 2402.17148 (MPS generative), 2304.12501 (TN predictor), 2007.00017 (TN portfolio)

---

## 1. Động cơ

Bản gốc có **nhiều báo giả** (đo thật, không phải 0%):
- Trên dải liên tục 2 tháng: **FP=275 / TP=21** (precision 7%)
- Fire trên control: busd 25%, euler 13%, crv near-miss 32–61%

Và bản gốc chỉ dùng **1/4 metric** mà bài CFI gốc dùng.

---

## 2. Nâng cấp đã thêm (song song core)

### 2a. Data cleaning — `engine/cfi/clean.py`
Theo §II.B–C của bài 2601.08540: **winsorize 0.5%** + **MAD-clip (k=12)** trên ma trận
returns trước khi tính tương quan → loại spike kỹ thuật / thin-pool tạo tương quan giả
(nguồn báo giả chính).

### 2b. PCA-CFI 4 metric — `engine/cfi/indicator.py`
Bài gốc định nghĩa CFI từ **4 metric bổ trợ** hợp nhất bằng **PCA (PC1)**:
1. `average_strength` — đồng bộ toàn hệ
2. `max_eigenvalue` — mode chung áp đảo
3. `strong_edge_density` — liên kết mạnh bất thường (|C|>0.3)
4. `eigenvalue_entropy` — độ phân tán (thấp = mong manh)

`CFIModel.fit()` học mean/std + PC1 trên tập tham chiếu (luna+normal). Loadings đo được:
```
PC1 = [avg_str +0.52, max_eig +0.53, strong_edge +0.42, entropy −0.53]
```
→ **Khớp bài gốc** (3 metric dương, entropy âm) — upgrade cài đúng.

> Bản LOCKED cũ chỉ dùng metric #4 (`1 − entropy`). PCA 4 metric bền hơn với nhiễu.

---

## 3. Thí nghiệm A/B (đo trung thực)

Ba harness so sánh, **không đụng core**:
`tools/cfi_pca_eval.py`, `tools/cfi_ensemble_eval.py`, `tools/entropy_persist_eval.py`.

### 3a. PCA-CFI vs Entropy (`cfi_pca_eval`)
| Control | OLD (entropy) | NEW (PCA+clean) |
|---|---|---|
| busd_freeze | 23% | **0%** |
| euler_hack | 13% | **3%** |
| crv (aug/nov) | 30% / 58% | **0% / 2%** |

**Nhưng recall 7/7 → 5/7** (mất luna + may_2021). Cleaning làm mượt spike → diệt cả
spike báo-giả LẪN spike crisis thật (luna là loại "spiky"). → **tradeoff precision–recall**.

### 3b. Ensemble entropy × PCA-CFI gate (`cfi_ensemble_eval`)
Fire khi `entropy≥90 AND PCA-CFI≥G`. Sweep G:

| G | Crisis | busd | euler |
|---|---|---|---|
| 0 (entropy đơn) | 7/7 | 23% | 13% |
| 50 | 6/7 | **0%** | 3% |

**Chỉ mất đúng LUNA** — ngay G=5 đã rớt. Vì ở cửa sổ tiền-cascade của LUNA (depeg UST,
chưa lan rộng protocol), PCA-CFI ≈ 0 nên không xác nhận. → **Không thể vừa 7/7 vừa FP
thấp bằng gate này; cái giá là event chủ lực LUNA.**

### 3c. Persistence + Hysteresis trên entropy (`entropy_persist_eval`) — ĐƯỢC CHỌN
Fire khi **N cửa sổ RED liên tiếp**; giữ đến khi score < 70 (hysteresis). Sweep N:

| N | Crisis | busd (episodes) | euler |
|---|---|---|---|
| 1 (cũ) | 7/7 | 11 | 1 |
| **4** | **7/7** | **7** | 1 |
| 5 | 7/7 | 6 | 1 |

**Giữ 7/7 (cả LUNA) + giảm ~36% báo spam spiky.** busd không về 0 vì busd_freeze là
**stress on-chain THẬT, bền vững** (không phải spike) — persistence giữ nó là **đúng**.

---

## 4. Quyết định & thay đổi wired

| Hướng | Crisis | FP | LUNA | Kết luận |
|---|---|---|---|---|
| PCA-CFI thay thế | 5/7 | rất thấp | ❌ | Mất quá nhiều recall |
| Ensemble gate | 6/7 | ~0 | ❌ | Mất LUNA (event chủ lực) |
| **Persistence N=4** | **7/7** | vừa | ✅ | **Chọn** |

**Wired vào `emitter/orchestrator.py`:** `persistence=4`, `fire=90`, `clear=70`.
Alert bật sau 4 cửa sổ RED liên tiếp, giữ đến khi < 70. Không đụng core LOCKED (chỉ hậu
xử lý điểm số). PCA-CFI + cleaning giữ lại làm **tín hiệu phụ / nghiên cứu**.

---

## 5. Trung thực về giới hạn

- Persistence **trượt trên ROC** — giảm báo spam nhưng không thêm skill; busd/euler là
  stress thật nên không xoá được (và không nên giấu).
- PCA-CFI cắt FP mạnh **nhưng** không thấy LUNA-class (depeg sớm, tương quan chưa lan) →
  không dùng làm gate cứng.
- Không cải thiện ở **sai sân** (dự báo volume): CFI vẫn thua baseline B0 ở đó (xem
  `09_F1_HONEST_FINDINGS.md`).

---

## 6. Tái lập

```bash
python3 -m tools.cfi_pca_eval          # PCA-CFI vs entropy: FP giảm, recall 5/7
python3 -m tools.cfi_ensemble_eval     # ensemble gate: chỉ mất LUNA
python3 -m tools.entropy_persist_eval  # persistence N: giữ 7/7, giảm FP  ← đã wired
python3 -m tools.mps_filter_eval       # Tier-2 MPS generative OOD gate (mechanism demo)
python3 -m pytest tests/unit -q        # 59 tests pass
```

Files thêm: `engine/cfi/clean.py`, `engine/cfi/indicator.py`, `engine/mps/generative.py`,
`tools/{cfi_pca_eval,cfi_ensemble_eval,entropy_persist_eval,mps_filter_eval}.py`.
Sửa: `emitter/orchestrator.py` (persistence/hysteresis) + tests.

---

## 7. Tier 2 — MPS generative precision-filter

Theo arXiv:2402.17148 (MPS làm mô hình sinh cho chuỗi thời gian tài chính).

### Ý tưởng
Học **phân phối hành vi "normal"** của DeFi trên vector 4-metric CFI, biểu diễn bằng
**MPS / tensor-train** (TT-SVD của tensor mật độ thực nghiệm). Cửa sổ **likelihood thấp =
out-of-distribution (OOD) = bất thường**. Dùng làm **cổng precision**: chỉ xác nhận alert
khi window vừa fragile (entropy RED) vừa OOD.
- `engine/mps/generative.py` — `MPSBornDensity` (deterministic, pure numpy, không cần nhãn)
- Unsupervised → giữ tính honest + củng cố narrative tensor-network.

### Kết quả (gate: entropy≥90 AND OOD≥P) — train tạm trên `cont_q2_2022`
| anomaly P | Crisis | busd | euler |
|---|---|---|---|
| (none) | 7/7 | 23% | 13% |
| **90** | **7/7** | **5%** | **7%** |
| 95 | 6/7 | 1% | 2% |

**P90: giữ 7/7 (kể cả LUNA) + busd 23→5%, euler 13→7%** — tốt hơn PCA-CFI gate (mất LUNA)
và persistence (cắt busd/euler ít hơn). MPS giữ LUNA vì đo OOD theo **mật độ** (LUNA lệch
phân phối ở chiều khác), không phụ thuộc một gate tương quan đơn.

### So 3 hướng giảm FP (đều fixed-threshold, cùng giao thức)
| Hướng | Crisis | busd | euler | Giữ LUNA |
|---|---|---|---|---|
| PCA-CFI gate (G50) | 6/7 | ~0% | 3% | ❌ |
| Persistence N=5 (đã wired) | 7/7 | ~6 ep | 1 | ✅ |
| **MPS filter P90** | **7/7** | 23→5% | 13→7% | ✅ |

### ⚠️ Giới hạn — mới là MECHANISM DEMO
- **Train nhiễm bẩn:** `cont_q2_2022` **chứa** luna + stETH → 2 event đó là *in-sample* →
  detection của chúng bị **circular** (số busd/euler thì hợp lệ vì khác thời kỳ).
- Cần train trên **dải calm SẠCH không trùng test event** (seg1-3, đang extract) → số
  out-of-sample tin cậy.
- **Chưa wire** vào orchestrator — chờ số sạch.

### Định hướng sản phẩm
- **Pha 1 (giờ):** MPS generative làm **precision-filter không cần nhãn** — khả thi ngay,
  giảm FP, giữ honesty.
- **Pha 2 (khi đủ nhãn/multi-chain):** TN classifier (2304.12501) hợp nhất tín hiệu.
  **Chưa làm** vì chỉ 7 event → overfit. Không over-engineer: core CFI+RCS+persistence đã
  đủ cho một sản phẩm honest.
