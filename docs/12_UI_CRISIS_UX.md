# 12 — UI/UX: Hiển thị khủng hoảng rõ ràng & đáng tin

> Kết tinh từ phiên party-mode (Sally/John/Sophia/Amelia/Mary + Anti-Consensus Club).
> Nguyên tắc xuyên suốt của Nguyenquocbao: **trung thực trên hết** — rõ ràng ≠ luôn báo động.

## Quyết định đã chốt

### 1. Kênh cảnh báo = THÔNG BÁO (notification), không phải bảng số
- Người dùng không đọc dashboard trong hoảng loạn — họ đọc **một câu**.
- Thông báo **chỉ bắn theo confirmed-alert** (persistence N=4 cửa sổ RED liên tiếp,
  hysteresis clear ở 70) — đã có trong `emitter/orchestrator.py` + webhook fan-out.
  KHÔNG bắn theo score thô nhấp nháy 90 một giây.

### 2. Cấu trúc thông báo = 1 câu chuyện cụ thể + 1 hành động
- Nêu **đích danh tâm chấn** (RCS) — nhưng **chỉ khi** top-1 ≫ top-2 (chênh contribution
  vượt ngưỡng). Không đủ chắc → "nhiều giao thức đang đồng pha bất thường".
- Câu chữ **trung thực về độ chắc**: không viết "bạn còn 16 giờ" như đồng hồ đếm ngược;
  viết "tín hiệu thường xuất hiện ~16h trước cascade trong lịch sử".
- Kết bằng một **động từ** + nút mở đúng trang extension.

### 3. Thông báo → "CHO TÔI XEM ĐỂ TÔI QUYẾT" (advisor, không auto)
- Người dùng mục tiêu = trader tự quyết. `ProtectionMode` mặc định **advisor**
  (đã có `off/advisor/auto` trong code). Auto-protection lùi xuống làm cố vấn: đề xuất,
  không bấm hộ.

### 4. Màn hình quyết định = 3 NHỊP (thứ tự cố định)
1. **Cái gì đang vỡ** *(dòng to nhất — Sophia thắng)*
   → Tiêu đề = **ANALOG**, không phải phần trăm (xem mục 5).
2. **Phần của bạn** *(ngay dưới, KHÔNG cuộn — Sally giữ)*
   → "12% danh mục dính ETH · lỗ ước tính…".
3. **Còn bao lâu + hành động** *(John)*
   → "cascade 41% · lịch sử đi trước ~16h" + nút **"Xem 3 vị thế rủi ro →"**.
- **Trạng thái AN TOÀN (bắt buộc — Mary):** nếu người dùng không phơi nhiễm,
  nói thẳng **"Thị trường căng, nhưng bạn gần như không phơi nhiễm — rủi ro của bạn: thấp"**.
  KHÔNG nhuộm đỏ cả màn. Dám nói "bạn ổn" mới đáng tin khi nói "bạn nguy".
- Nến / oscillator / lưới 13×13 nằm **dưới nếp gấp** cho người muốn đào.

### 5. Tiêu đề = ANALOG CRISIS (Wildcard, đổi trục niềm tin)
Con người không tin "41%"; con người tin *"tôi đã thấy phim này rồi, và nó kết tệ."*
- **Đặc trưng/cửa sổ (gọi tên được):** `score`, `độ dốc score`, `breadth (N/13)`,
  `loại tâm chấn` (vd. lending). 3–4 chiều, tất cả đã có trong `build_timeline`.
- **Nearest-neighbor** tới thư viện các cửa sổ *tiền-cascade* của 7 crisis đã bắt được.
- **BẮT BUỘC kèm khoảng cách + ngưỡng.** Dưới ngưỡng gần → tiêu đề lùi về
  **"Mẫu hình bất thường nhưng không khớp khủng hoảng đã biết"** (vẫn cảnh báo,
  không giả vờ biết kết cục).
- **Hình:** sparkline chồng đường score *bây giờ* lên *LUNA hồi đó*.
- Ví dụ tiêu đề: **"⚠ Giống LUNA ở T‑16h trước sụp — cùng độ lan & tâm chấn lending (khoảng cách 0.2, rất gần)"**.

## Chốt chặn TRUNG THỰC (Level + Mary + Splinter)
- **41% & ~16h fit trên `cont_q2_2022` proxy** → chưa in như sự thật cứng. Hạ giọng
  ("rủi ro cao — mô hình sơ bộ") cho tới khi có dữ liệu calm sạch.
- **~16h** có thể là lead của LUNA, n nhỏ → cần khoảng, không trình như quy luật.
- **Nearest-neighbor trên 7 mẫu luôn trả về "một cái gì đó"** (ép mặt vào mây) →
  ngưỡng "không-analog" là **bắt buộc**.
- **Đừng leo lên distance ma trận 13×13** — overfit thư viện tí hon; 4 đặc trưng gọi
  tên được là đủ (Killjoy).

## Hoãn tới khi có dữ liệu (đang extract seg1/seg2/seg3)
- Calibrate **ngưỡng analog** từ khoảng cách của các cửa sổ *calm* tới thư viện crisis.
- Re-fit MPS scenario/filter/price trên calm data sạch → khi đó mới chốt 41%/16h.
- **Hôm nay build được CƠ CHẾ** (vector đặc trưng + nearest-neighbor + trạng thái
  "không-analog"); **số ngưỡng để trống chờ dữ liệu.**
