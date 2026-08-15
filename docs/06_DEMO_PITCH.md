# Demo & Pitch — 5 phút

## Pitch structure (5 phút)

### 1. Hook (30s)
> "Tháng 5/2022, LUNA sụp đổ và kéo theo $400M thanh lý dây chuyền trên DeFi trong
> 72 giờ. Các risk team KHÔNG có công cụ cảnh báo sớm. Chúng tôi xây dựng nó."

### 2. Problem (45s)
- DeFi lending = rủi ro cascade liquidation
- Công cụ hiện có (Gauntlet, Nansen) = báo cáo định kỳ, không realtime
- Risk team cần: **cảnh báo TRƯỚC khi cascade, biết protocol nào là tâm chấn**

### 3. Solution + Insight (60s)
> "Khủng hoảng = mọi protocol biến động đồng bộ. Bình thường hoạt động độc lập.
> Chúng tôi đo mức độ đồng bộ này bằng **correlation network + tensor-network method
> (MPS)** — mượn từ vật lý lượng tử."

```
on-chain events → correlation matrix → eigenvalue entropy
              → fragility score → alert + RCS (tâm chấn)
```

### 4. Proof (90s) — QUAN TRỌNG NHẤT
> "Chúng tôi test trên **12 sự kiện lịch sử thật** từ Ethereum mainnet."

**Slide bằng chứng:**
```
7/7 khủng hoảng dự báo được TRƯỚC cascade (lead 10-66h)
0% false positive trên thị trường bình thường
RCS chỉ đúng tâm chấn: LUNA → cUSDC + DAI/WETH
```

**Live demo:** chạy `honest_detection_count` hoặc dashboard.

### 5. Vision + Ask (45s)
- v1: on-chain cascade (done, proven)
- v2: off-chain fusion (FTX-class), multi-chain
- Ask: "Early-warning system đầu tiên dùng tensor-network realtime on-chain."

---

## Live demo commands

```bash
# Option A: Terminal — honest detection (nhanh, thuyết phục)
python3 -m tools.honest_detection_count
# → show 7/7 crisis + 0% FP live

# Option B: Dashboard (visual)
python3 -m demo.dashboard   # localhost:8080
# → LUNA replay, score leo lên RED trước cascade, RCS panel
```

---

## Câu hỏi judge có thể hỏi + trả lời

**Q: Sao không dùng ML/deep learning?**
> Correlation-network fragility có prior art vật lý (arXiv 2601.08540), interpretable,
> không cần training data lớn, chạy CPU realtime. RCS cho explainability mà black-box
> ML không có.

**Q: Overfit không? Test trên bao nhiêu data?**
> Calibrate chỉ trên LUNA+Normal (2 fixture). Test out-of-sample trên 10 fixture khác
> → 7/7 crisis detect. Trung thực: calibration có thể tune tốt hơn, và detection một
> số case là "spiky" (mean thấp, spike lẻ).

**Q: Đã test out-of-sample liên tục chưa? So với baseline thế nào? (câu hỏi khó)**
> Rồi — và chúng tôi công bố cả null-result. Dựng F1 out-of-sample nghiêm ngặt (nhãn
> liquidation-cascade on-chain khách quan, time-split + embargo, baseline B0, bootstrap
> CI) trên dải liên tục 2 tháng (641k sự kiện). **Phát hiện trung thực: để dự báo KHỐI
> LƯỢNG thanh lý, baseline đếm-borrow thắng (AUC 0.77 vs 0.48)** — vì volume tự tương
> quan. Điều đó khẳng định **ranh giới đúng** của sản phẩm: chúng tôi đo *cấu trúc tương
> quan hệ thống*, không đo mức độ hoạt động. Ở đúng bài toán của mình — phát hiện các
> cascade hệ thống lớn — event-level cho 7/7 kể cả FTX mà B0 miss. Chi tiết:
> `09_F1_HONEST_FINDINGS.md`.

**Q: FTX là off-chain, sao bắt được?**
> Chúng tôi KHÔNG bắt FTX fraud (off-chain). Chúng tôi bắt **ETH price cascade on-chain
> đi kèm** FTX week (~37h trước). Trung thực về ranh giới này.

**Q: False positive thế nào?**
> Normal market: 0%. busd_freeze fire 25% nhưng đó là BUSD panic exit — stress on-chain
> thật, không phải báo động giả thuần. Euler chỉ fire SAU exploit.

**Q: Realtime chạy được không?**
> Có. Correlation matrix 13×13 = tính trong <10ms. Pipeline WSS → orchestrator →
> webhook đã build. Cần ~4500 block history (~16h) để warm up.

---

## Điểm nhấn khác biệt (nếu bị so sánh)

| | Đối thủ (Gauntlet/Nansen) | QuantumRadar |
|-|---------------------------|--------------|
| Realtime | ❌ báo cáo định kỳ | ✅ webhook |
| Method | Simulation/heuristic | Tensor-network (novel) |
| Explainability | Report | ✅ RCS per-protocol |
| Systemic view | Per-position | ✅ Cross-protocol correlation |

---

## KHÔNG nói (tránh overclaim)

- ĐỪNG nói "dự báo được MỌI khủng hoảng" → chỉ on-chain cascade
- ĐỪNG nói "bắt được FTX fraud" → chỉ ETH cascade đi kèm
- ĐỪNG dùng số "6/6" từ p80-metric (ẢO) → dùng "7/7 fixed-threshold"
- ĐỪNG giấu điểm yếu spiky → judge kỹ thuật sẽ hỏi, trung thực ghi điểm
- ĐỪNG nói "F1 cao hơn baseline" → continuous F1 (dự báo volume thanh lý) baseline B0
  thắng; ta chỉ hơn ở **event-level** (7/7, FTX). Trung thực scope, đừng thổi phồng.
- ĐỪNG nói "dự báo khối lượng thanh lý" → đo cấu trúc tương quan hệ thống, không đo volume

---

## Backup slide: Tech stack

- Python, numpy, scikit-learn (Ledoit-Wolf), FastAPI
- 537 LOC core algorithm, 661 tests
- 12 fixtures thật từ Etherscan (LUNA → CRV 2023)
- CPU-only, no GPU, realtime-capable
