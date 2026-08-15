"""Sweep chi × fit_window to confirm the optimal config (Story 2.4, FR12).

For each (chi, fit_window) it measures separation between LUNA (crisis) and NORMAL
(FP control): gap = luna_p80 - normal_max. FP-safe requires normal_max < luna_p80.
Expected winner: chi=None, fit_window=40 (best gap + FP-safe). chi<4 inverts signal.
"""
import sys
from pathlib import Path

import numpy as np

from ingestion.csv_loader import load_events
from tools._common import raw_rolling

FIXTURE_DIR = Path("fixtures/backtest")
LUNA = "luna_2022_05_09"
NORMAL = "normal_2023_03_15"

CHIS = [None, 2, 3, 4, 6]
FIT_WINDOWS = [20, 30, 40, 60]


def _events(name):
    path = FIXTURE_DIR / f"{name}.csv.gz"
    if not path.exists():
        print(f"ERROR: missing fixture {path} — run tools.extract_fixtures first", file=sys.stderr)
        return None
    return load_events(str(path))


def main():
    luna_ev, normal_ev = _events(LUNA), _events(NORMAL)
    if luna_ev is None or normal_ev is None:
        return 2

    print("=== CFI+MPS Sweep (separation LUNA vs NORMAL) ===")
    print(f"{'chi':>5} {'fit_win':>8} {'normal_max':>11} {'luna_p80':>10} {'gap':>10} {'FP-safe':>8}")
    rows = []
    for chi in CHIS:
        for fw in FIT_WINDOWS:
            luna = raw_rolling(luna_ev, fit_window=fw, chi=chi)
            normal = raw_rolling(normal_ev, fit_window=fw, chi=chi)
            if not luna or not normal:
                continue
            nmax = float(np.max(normal))
            lp80 = float(np.percentile(luna, 80))
            gap = lp80 - nmax
            safe = nmax < lp80
            rows.append((chi, fw, nmax, lp80, gap, safe))
            print(f"{str(chi):>5} {fw:>8} {nmax:>11.6f} {lp80:>10.6f} {gap:>10.6f} {('YES' if safe else 'NO'):>8}")

    safe_rows = [r for r in rows if r[5]]
    if safe_rows:
        best = max(safe_rows, key=lambda r: r[4])
        print()
        print(f"→ Best FP-safe separation: chi={best[0]}, fit_window={best[1]} (gap={best[4]:.6f})")
        if best[0] is None and best[1] == 40:
            print("  ✓ Matches LOCKED config (chi=None, fit_window=40).")
        else:
            print("  ⚠ Differs from LOCKED (chi=None, fit_window=40) — LOCKED stays authoritative (NFR2).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
