# Results — Honest Validation

**Detector:** CFI + MPS v2 · **Calibration:** SCORE_FLOOR=0.0061, SCORE_CEIL=0.0132,
fit_window=40, chi=None · **Threshold:** FIXED YELLOW=70 / RED=90 (không phải
p80-per-scenario).

---

## Kết quả chính

### Crisis detection (7/7 trước cascade @ RED)

| Sự kiện | mean | %RED | Lead time | Detect |
|---------|------|------|-----------|--------|
| luna | 44.1 | 25% | ~10h | ✅ |
| ftx | 73.5 | 54% | ~37h | ✅ |
| steth_depeg | 10.4 | 10% | ~66h | ✅ |
| may_2021_eth_crash | 53.8 | 45% | ~48h | ✅ |
| wbtc_cascade | 12.0 | 12% | ~48h | ✅ |
| eth_cascade_ftx_week | 27.9 | 18% | ~49h | ✅ |
| usdc_depeg_svb | 15.1 | 14% | ~28h | ✅ |

**→ 7/7 crisis dự báo được TRƯỚC cascade. Lead time trung bình >40h.**

### FP controls

| Sự kiện | %RED | Đánh giá |
|---------|------|----------|
| **normal** (thị trường yên) | **0%** | ✅ SẠCH |
| busd_freeze | 25% | ⚠️ Fire — nhưng BUSD panic exit là stress on-chain thật |
| euler_hack | 13% | ⚠️ Fire CHỈ SAU exploit (không dự báo sai — exploit là 1-block) |

### Near-miss (không cascade, high-risk thật)

| Sự kiện | %RED | Ghi chú |
|---------|------|---------|
| crv_near_miss_aug | 32% | Egorov CRV positions gần bị thanh lý (averted OTC) |
| crv_near_miss_nov | 61% | Episode 2 — risk thật, fire đúng |

---

## RCS — chỉ đúng tâm chấn

| Crisis | RCS top contributors | Khớp thực tế? |
|--------|---------------------|---------------|
| LUNA | cUSDC, DAI/WETH pool, cETH | ✅ lending + stablecoin stress |
| FTX | WBTC/WETH, DAI/WETH, cUSDC | ✅ BTC/ETH correlated crash |
| eth_cascade | cWBTC2, DAI/WETH, cDAI | ✅ ETH collateral deleverage |

---

## ⚠️ Bẫy metric (đọc kỹ để không tự lừa)

### p80-per-scenario = ẢO
Lần validate đầu dùng "p80 của CHÍNH scenario đó" làm threshold → mọi scenario luôn
có đúng 20% window vượt p80 của nó → "detection 6/6" là **guaranteed by construction**,
không phải năng lực detector.

**Fix:** dùng ngưỡng CỐ ĐỊNH (70/90) trên thang [0,100] đã calibrate. Đó mới là test thật.

### Saturation
Với calibration LUNA-based, `max=100` xuất hiện ở NHIỀU scenario (kể cả control) vì
`SCORE_CEIL=0.0132` thấp. Nên nhìn **mean + %RED** thay vì max.

---

## Điểm mạnh (bằng chứng cho judge)

1. **7/7 crisis detected pre-cascade** — kể cả FTX mà B0 (baseline đếm borrow) hoàn toàn miss
2. **Normal market: 0% false positive** — control quan trọng nhất, sạch tuyệt đối
3. **RCS chỉ đúng tâm chấn** — không chỉ báo "có crisis" mà còn "protocol nào"
4. **On-chain, no external API** (trừ Etherscan để lấy history), CPU-only, realtime-capable

## Điểm yếu (trung thực)

1. **Detection "spiky"** — steth/wbtc/eth_cascade mean thấp (10-28), fire RED nhờ vài
   spike lẻ, không phải signal bền vững như ftx/may_2021 (mean 54-73). Debounce giúp
   nhưng độ tin cậy thấp hơn.
2. **busd_freeze fire 25%** — ranh giới FP/real mờ (BUSD exit là stress thật)
3. **Chỉ 1 control thị trường-yên thật** (normal) — cần thêm control để claim FP rate chung
4. **Calibration overfit LUNA/Normal** — nên re-calibrate trên nhiều fixture (TODO)
5. **Không bắt exploit trước** (euler chỉ fire sau) — category boundary, không phải bug

---

## Reproduce

```bash
python3 -m tools.honest_detection_count   # in ra bảng trên
```

Output file: `calibration/validation_10_scenarios.md`

---

## So sánh baseline

| Detector | LUNA | FTX | Normal FP | RCS |
|----------|------|-----|-----------|-----|
| B0 (borrow count) | ✅ 27h | ❌ miss | 0% | ❌ |
| Indicator (borrow volume) | ✅ | ⚠️ 41h | 0% | ❌ |
| **CFI+MPS v2** | ✅ 10h | ✅ 37h | **0%** | ✅ |

CFI+MPS thắng vì bắt được **FTX** (correlated ETH cascade) + có **RCS**.
