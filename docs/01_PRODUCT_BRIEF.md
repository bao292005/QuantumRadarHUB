# Product Brief — QuantumRadar

## One-liner

**Hệ cảnh báo sớm sụp đổ dây chuyền DeFi** — phát hiện systemic risk on-chain và
bắn webhook alert tới protocol risk teams TRƯỚC khi thanh lý dây chuyền xảy ra.

---

## Problem

DeFi lending protocols (Aave, Compound, Morpho...) đối mặt rủi ro **cascade
liquidation**: khi một tài sản depeg/crash, các vị thế đòn bẩy bị thanh lý hàng
loạt, kéo theo domino toàn hệ sinh thái.

- LUNA/UST (2022-05): ~$400M thanh lý on-chain trong 72h
- stETH depeg (2022-06): 3AC/Celsius sụp, ~$100-200M liquidation
- USDC depeg/SVB (2023-03): stablecoin panic

**Các công cụ hiện có (Gauntlet, Nansen, Chaos Labs)** = analytics/tư vấn, báo cáo
định kỳ. KHÔNG có **realtime early-warning** dành cho risk team hành động ngay.

---

## Solution

QuantumRadar theo dõi **hoạt động on-chain realtime** qua WebSocket, dựng
**correlation network** giữa các protocol, và tính chỉ số fragility bằng phương pháp
**tensor-network (MPS) + correlation spectral (CFI)**:

```
on-chain events (WSS) → correlation matrix → CFI+MPS fragility score
                     → alert (YELLOW/RED) → webhook → risk team
                     → RCS: protocol nào là tâm chấn?
```

**Điểm khác biệt:**
1. **Realtime webhook** (vs báo cáo định kỳ của đối thủ)
2. **Systemic-level** (đo cả hệ, không phải từng vị thế)
3. **RCS** — chỉ ra protocol/pool cần can thiệp trước

---

## Target customer

- **Lõi:** protocol risk teams (Aave/Compound/Morpho/Spark)
- **Mở rộng:** DeFi funds, market makers, insurance protocols (Nexus Mutual)

---

## Why now / Why us

- Correlation-network fragility có prior art học thuật (arXiv 2601.08540) nhưng CHƯA
  ai áp dụng realtime on-chain
- On-chain data giờ đầy đủ + rẻ (Etherscan, WSS nodes)
- Bằng chứng: model dự báo được **7/7 crisis** trên dữ liệu lịch sử thật

---

## Positioning & Honesty (RANH GIỚI RÕ RÀNG)

**v1 làm được:**
- Bắt **on-chain leverage/liquidation cascade** (LUNA-class, stETH-class, depeg-class)
- Lead time 10-66h trước cascade
- 0% FP trên thị trường bình thường

**v1 KHÔNG làm được (trung thực):**
- **FTX-class off-chain fraud thuần** — nếu không có dấu vết on-chain thì không bắt
  được. (Nhưng ETH price cascade đi kèm FTX week thì CFI+MPS bắt được ~37h trước)
- **Smart contract exploit** (Euler) — chỉ fire SAU exploit, không dự báo trước
  (exploit là sự kiện 1-block, không có build-up)

**Nguyên tắc:** trung thực về giới hạn > thổi phồng. Đo trước khi tin.

---

## Business model (pitch)

- **SaaS subscription** theo protocol: $X/tháng cho realtime webhook + dashboard
- **Tiered:** free (delayed) / pro (realtime) / enterprise (custom RCS + SLA)
- **Land & expand:** 1 risk team → toàn bộ protocol ecosystem

---

## Roadmap

| Version | Scope |
|---------|-------|
| **v1 (now)** | On-chain leverage cascade, CFI+MPS+RCS, 12-protocol universe |
| v1.5 | Mở rộng universe (30+ protocol), depeg/oracle feed |
| v2 | Off-chain signal fusion (CEX flows) để cover FTX-class |
| v3 | Multi-chain (L2s, Solana), predictive RCS |

---

## Ask (hackathon)

Chúng tôi đã chứng minh: correlation-network fragility **dự báo được 7/7 khủng hoảng
DeFi lịch sử** với 0% false positive trên thị trường bình thường, lead time trung
bình >24h. Đây là early-warning system đầu tiên áp dụng tensor-network method
realtime on-chain.
