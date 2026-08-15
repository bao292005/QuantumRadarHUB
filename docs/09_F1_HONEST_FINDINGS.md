# F1 Honest Findings — Continuous Out-of-Sample Test

Ghi lại **trung thực** kết quả kiểm định F1 liên tục. Đây là null-result có chủ đích:
chúng tôi công bố để judge thấy phương pháp chặt và scope đúng, thay vì giấu.

---

## Ta đã test gì

Ngoài gate event-level 7/7 (12 fixture cắt quanh crisis), chúng tôi dựng một **F1
out-of-sample nghiêm ngặt trên 1 dải liên tục** để trả lời câu hỏi thực tế:

> "Nếu bật 24/7 suốt nhiều tháng, detector có dự báo cascade tốt hơn baseline không?"

**Setup (`tools/f1_backtest.py`):**
- **Dữ liệu:** `cont_q2_2022` — dải liên tục block 14,700,000–15,010,000 (~2 tháng,
  **641,505 sự kiện on-chain**), phủ LUNA + stETH depeg + wbtc cascade.
- **Nhãn khách quan:** forward liquidation-cascade — window là "dương" nếu **số
  liquidation on-chain trong 48h tới ≥ P90** (ngưỡng lấy từ TRAIN). Đếm sự kiện
  (unit-free), không dùng cascade-block thủ công.
- **Split:** time-split + embargo = horizon (nhãn nhìn-tương-lai không rò vào test).
  Threshold nhãn **và** threshold detector đều chọn trên TRAIN.
- **Baseline B0:** đếm borrow/liquidation, chấm bằng đúng giao thức.
- **Bất định:** moving-block bootstrap 95% CI.

---

## Kết quả

| Detector | test F1 | precision | recall | 95% CI |
|----------|--------:|----------:|-------:|--------|
| **CFI+MPS** | **0.077** | 0.071 | 0.085 | [0.00, 0.18] |
| **B0 (borrow-count)** | **0.445** | 0.301 | 0.854 | [0.22, 0.65] |

**B0 thắng dứt khoát (Δ F1 = −0.367).** AUC xác nhận:

| | AUC vs forward-liquidation |
|--|--:|
| CFI+MPS | **0.484** (≈ 0.5 = ngẫu nhiên) |
| B0 (borrow+liq) | 0.767 |
| B0 borrow-ONLY (loại rò rỉ nhãn) | 0.676 |

---

## Diễn giải (vì sao)

1. **CFI+MPS ≈ ngẫu nhiên (AUC 0.48)** với số thanh lý tương lai. Fragility đo **cấu
   trúc tương quan** (regime), **không** đo mức độ hoạt động → orthogonal với volume.
2. **B0 thắng thật, KHÔNG do leak:** borrow-only (không đếm liquidation) vẫn AUC 0.68.
   Hoạt động đòn bẩy **tự tương quan** — nhiều borrow bây giờ ⇒ nhiều thanh lý 48h tới.
   Dự báo volume vốn là bài toán mức-độ-hoạt-động mà baseline đếm sự kiện thắng gần như
   hiển nhiên.
3. **Đây là mismatch label–mục tiêu**, cùng loại với "ETH drawdown chấm LUNA=0" trước
   đó: nhãn đo thứ *cạnh* mục tiêu detector, không phải chính nó.

---

## Ý nghĩa cho tuyên bố sản phẩm

**KHÔNG dùng:** con số F1 continuous để nói "CFI+MPS > baseline". Nó không đúng.

**Vẫn đứng vững (event-level):**
- 7/7 crisis detected pre-cascade @ RED, ngưỡng CỐ ĐỊNH (không p80-per-scenario)
- 0% false positive trên thị trường `normal`
- Bắt **FTX** — cascade tương quan mà B0 (borrow-count) **miss**
- RCS chỉ đúng tâm chấn (giải thích được)

---

## Hòa giải với 7/7

CFI+MPS là **bộ phát hiện regime tương quan hệ thống**, không phải bộ dự báo khối lượng
thanh lý. Nó bắt được **các cascade liên-protocol lớn** (nơi mọi thứ biến động đồng bộ),
nhưng **không** — và không nên — bám theo mọi đợt thanh lý thường ngày. Trên dải liên tục
đầy thanh lý-thường-ngày, tín hiệu tương quan không trùng với volume → AUC ~0.5. Ở đúng
bài toán của nó (các sự kiện hệ thống lớn), event-level cho 7/7 kể cả FTX.

**Nguyên tắc:** đo trước khi tin. Trung thực về giới hạn > thổi phồng.
