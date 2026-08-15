# Algorithm Spec — CFI + MPS + RCS

Reference: arXiv 2601.08540 (Correlation Fragility Index). QuantumRadar adapts it to
**on-chain event data** and unifies it with a **Matrix Product State (MPS)** spectral
score.

---

## Core intuition

> **Khủng hoảng = mọi protocol biến động ĐỒNG BỘ.**

Bình thường, hoạt động của các protocol (Aave borrow, Uniswap swap, Compound...)
độc lập → correlation matrix "phẳng", nhiều eigenvalue gần bằng nhau → **entropy cao**.

Khi crisis, mọi thứ chuyển động cùng chiều (ai cũng bán, ai cũng thanh lý) →
correlation matrix "tập trung" vào 1 common mode → 1 eigenvalue lớn áp đảo →
**entropy thấp** → **fragility cao**.

```
fragility_score = 1 − normalized_entropy(eigenvalues(correlation_matrix))
```

---

## Pipeline tổng thể

```
1. on-chain events (list of dicts, 11-field tick schema)
        ↓  engine/cfi/onchain.py
2. build_activity_matrix   → (N_contracts × T_windows) — |amount0| per contract per window
        ↓
3. build_returns_matrix    → log(activity_t / activity_{t-1})    (N × T-1)
        ↓  engine/mps/v2.py
4. shrinkage_correlation   → C (N×N) Ledoit-Wolf correlation matrix
        ↓
5. eigvalsh(C) → λ_1 ≥ ... ≥ λ_N     (optional: truncate top-χ = bond dim)
        ↓
6. p_k = λ_k / Σλ_k        (Born probabilities)
        ↓
7. S = −Σ p_k ln(p_k) / ln(N)        (von Neumann entropy, normalized [0,1])
        ↓
8. fragility_raw = 1 − S             (HIGH = concentrated = crisis)
        ↓
9. score_100 = 100·clamp((raw − FLOOR)/(CEIL − FLOOR), 0, 1)
        ↓
10. alert_level: RED ≥ 90, YELLOW ≥ 70
```

**RCS (Risk Contribution Score)** — leave-one-out:
```
RCS[i] = fragility_raw(full) − fragility_raw(without contract_i)
Positive → contract i khuếch đại systemic risk (tâm chấn)
```

---

## Calibration constants (LOCKED)

```python
SCORE_FLOOR = 0.0061   # normal_max → score 0
SCORE_CEIL  = 0.0132   # luna_p80   → score 100
FIT_WINDOW  = 40       # return-windows mỗi scoring window
WINDOW_BLOCKS = 300    # blocks mỗi activity window (~65 min)
STRIDE_BLOCKS = 100    # stride giữa windows
CHI = None             # bond dim: None=full rank (best); chi<4 đảo signal
```

Sweep đã xác nhận `chi=None, fit_window=40` cho gap tốt nhất + FP-safe.

---

## Core code 1: Correlation spectral metrics

`engine/cfi/correlation.py` (106 LOC)

```python
import numpy as np
_EPS = 1e-12

def shrinkage_correlation(returns_by_asset: np.ndarray) -> np.ndarray:
    """Ledoit-Wolf shrinkage correlation. Input (N,T), output (N,N)."""
    x = np.asarray(returns_by_asset, dtype=float).T  # (T,N)
    if x.shape[0] < 2:
        raise ValueError("need >= 2 time observations")
    try:
        from sklearn.covariance import LedoitWolf
        cov = LedoitWolf(assume_centered=False).fit(x).covariance_
    except Exception:
        cov = np.cov(x, rowvar=False)
    d = np.sqrt(np.clip(np.diag(cov), _EPS, None))
    corr = cov / np.outer(d, d)
    np.fill_diagonal(corr, 1.0)
    return np.clip(corr, -1.0, 1.0)

def eigenvalue_entropy(corr: np.ndarray) -> float:
    """H = -1/ln N · Σ p_k ln p_k. LOW = concentrated = fragile. In [0,1]."""
    ev = np.clip(np.linalg.eigvalsh(corr), _EPS, None)
    p = ev / ev.sum()
    return float(-(p * np.log(p)).sum() / np.log(corr.shape[0]))

def max_eigenvalue(corr, *, normalize=True):
    lam = float(np.linalg.eigvalsh(corr).max())
    return lam / corr.shape[0] if normalize else lam

def average_strength(corr):
    n = corr.shape[0]; a = np.abs(corr).copy(); np.fill_diagonal(a, 0.0)
    return float(a.sum() / (n*(n-1)))

def strong_edge_density(corr, *, rho=0.3):
    n = corr.shape[0]; a = np.abs(corr).copy(); np.fill_diagonal(a, 0.0)
    return float((a > rho).sum() / (n*(n-1)))
```

---

## Core code 2: On-chain returns builder

`engine/cfi/onchain.py` (144 LOC) — key functions:

```python
import bisect, numpy as np
from collections import defaultdict
_EPS = 1e-30

def _contract_activity(events, contract_addr):
    addr = contract_addr.lower(); total = 0.0
    for e in events:
        if e.get("pool_address","").lower() == addr:
            try: total += abs(float(e.get("amount0") or 0))
            except (ValueError, TypeError): pass
    return total

def build_activity_matrix(events, contracts, *, window_blocks=300, stride_blocks=100):
    """(N_contracts × T_windows) raw activity volume."""
    if not events: return np.zeros((len(contracts), 0))
    blocks = [int(e["block_number"]) for e in events]
    lo, hi = blocks[0], blocks[-1]
    windows = []
    b = lo + window_blocks
    while b <= hi:
        li = bisect.bisect_left(blocks, b - window_blocks)
        ri = bisect.bisect_right(blocks, b)
        windows.append(events[li:ri]); b += stride_blocks
    if not windows: return np.zeros((len(contracts), 0))
    A = np.zeros((len(contracts), len(windows)))
    for j, win in enumerate(windows):
        for i, addr in enumerate(contracts):
            A[i,j] = _contract_activity(win, addr)
    return A

def build_returns_matrix(events, contracts, *, window_blocks=300, stride_blocks=100):
    """(N × T-1) log-returns of activity."""
    A = build_activity_matrix(events, contracts, window_blocks=window_blocks, stride_blocks=stride_blocks)
    if A.shape[1] < 2: return np.zeros((len(contracts), 0))
    A_safe = A + _EPS
    return np.log(A_safe[:,1:] / A_safe[:,:-1])

def active_contracts(events, min_windows_active=5, **kw):
    """Contracts appearing in >= min_windows_active windows."""
    addrs = list({e.get("pool_address","").lower() for e in events if e.get("pool_address")})
    if not addrs: return []
    A = build_activity_matrix(events, addrs, **kw)
    return [a for a, row in zip(addrs, A) if (row > 0).sum() >= min_windows_active]
```

---

## Core code 3: MPS correlation score + RCS

`engine/mps/v2.py` (180 LOC) — key functions:

```python
import numpy as np
from engine.cfi.correlation import shrinkage_correlation
_EPS = 1e-12

def _entropy_from_corr(C, chi):
    ev = np.linalg.eigvalsh(C); ev = np.clip(ev, _EPS, None)[::-1]  # descending
    if chi is not None and chi < len(ev): ev = ev[:chi]
    n = len(ev)
    if n <= 1: return 0.0
    p = np.clip(ev/ev.sum(), _EPS, 1.0)
    return float(-(p*np.log(p)).sum()) / np.log(n)

def mps_correlation_score(returns_window, *, chi=None):
    """(N,T) returns → fragility [0,1]. HIGH = concentrated = crisis."""
    R = np.asarray(returns_window, dtype=float)
    if R.ndim != 2: raise ValueError("returns_window must be 2-D")
    n, t = R.shape
    if n < 2 or t < 2: return 0.0
    mask = R.std(axis=1) > _EPS  # drop constant rows
    R = R[mask]
    if R.shape[0] < 2: return 0.0
    try: C = shrinkage_correlation(R)
    except Exception: return 0.0
    return 1.0 - _entropy_from_corr(C, chi)

def rcs_scores(returns_window, contract_labels=None, *, chi=None):
    """Leave-one-out risk contribution per contract."""
    R = np.asarray(returns_window, dtype=float); n = R.shape[0]
    labels = contract_labels or [str(i) for i in range(n)]
    full = mps_correlation_score(R, chi=chi)
    rcs = {lbl: full - mps_correlation_score(np.delete(R, i, axis=0), chi=chi)
           for i, lbl in enumerate(labels)}
    return dict(sorted(rcs.items(), key=lambda kv: kv[1], reverse=True))

def rolling_scores(returns, *, fit_window=40, score_stride=1, chi=None):
    """Score every rolling window."""
    R = np.asarray(returns, dtype=float); _, T = R.shape
    return [mps_correlation_score(R[:, t:t+fit_window], chi=chi)
            for t in range(0, T - fit_window + 1, score_stride)]
```

---

## Score → alert mapping

```python
def score_100(raw):
    span = SCORE_CEIL - SCORE_FLOOR
    return 100.0 * max(0.0, min(1.0, (raw - SCORE_FLOOR) / span))

def alert_level(s):  # from emitter/payload.py
    if s >= 90: return "RED"
    if s >= 70: return "YELLOW"
    return None
```

---

## Tại sao cách này thắng các approach khác

| Approach | Vấn đề | CFI+MPS fix |
|----------|--------|-------------|
| B0 (borrow count) | Miss FTX, chỉ đếm 1 protocol | Đo tương quan liên-protocol |
| MPS v1 (graph entropy) | Signal đảo (crisis=low entropy nhưng model đọc ngược) | Invert: 1−entropy |
| CFI (TVL từ DeFiLlama) | Chỉ 8 node, daily, external API | On-chain block-level, 13 node, no API |

**Đột phá:** dùng **on-chain activity log-returns** (không phải TVL) làm input cho
correlation matrix → block-level granularity + 13 protocol universe + no external dep.
