"""Calibrate SCORE_FLOOR / SCORE_CEIL on luna + normal (Story 2.3, FR11).

Method (docs/03_BUILD_GUIDE.md):
    1. rolling raw scores on LUNA + NORMAL (fit_window=40, chi=None)
    2. SCORE_FLOOR = normal_max   → score 0
    3. SCORE_CEIL  = luna_p80     → score 100
    4. verify normal_max < luna_p80 (FP-safe)

Prints computed vs LOCKED constants. The LOCKED values in engine/scoring.py remain
authoritative (NFR2) — this tool re-derives them as a check, it does NOT overwrite.
"""
import sys
from pathlib import Path

import numpy as np

from ingestion.csv_loader import load_events
from engine.scoring import SCORE_FLOOR, SCORE_CEIL
from tools._common import raw_rolling

FIXTURE_DIR = Path("fixtures/backtest")
LUNA = "luna_2022_05_09"
NORMAL = "normal_2023_03_15"


def _raws(name):
    path = FIXTURE_DIR / f"{name}.csv.gz"
    if not path.exists():
        print(f"ERROR: missing fixture {path} — run tools.extract_fixtures first", file=sys.stderr)
        return None
    return raw_rolling(load_events(str(path)))


def main():
    luna = _raws(LUNA)
    normal = _raws(NORMAL)
    if not luna or not normal:
        return 2

    normal_max = float(np.max(normal))
    luna_p80 = float(np.percentile(luna, 80))
    fp_safe = normal_max < luna_p80

    print("=== CFI+MPS Calibration ===")
    print(f"LUNA windows scored   : {len(luna)}")
    print(f"NORMAL windows scored : {len(normal)}")
    print(f"normal_max (→ FLOOR)  : {normal_max:.6f}")
    print(f"luna_p80   (→ CEIL)   : {luna_p80:.6f}")
    print(f"FP-safe (normal<luna) : {'YES ✓' if fp_safe else 'NO ✗'}")
    print()
    print("--- computed vs LOCKED (engine/scoring.py) ---")
    print(f"FLOOR computed={normal_max:.6f}   LOCKED={SCORE_FLOOR}")
    print(f"CEIL  computed={luna_p80:.6f}   LOCKED={SCORE_CEIL}")
    print()
    print("NOTE: LOCKED constants stay authoritative (NFR2). Use computed values only")
    print("      to sanity-check; do not overwrite unless re-calibrating deliberately.")
    return 0 if fp_safe else 1


if __name__ == "__main__":
    raise SystemExit(main())
