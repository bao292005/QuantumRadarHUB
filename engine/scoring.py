"""Score→alert mapping + LOCKED calibration constants (Story 1.4).

Constants sourced verbatim from docs/02_ALGORITHM_SPEC.md "Calibration constants (LOCKED)".
Changing these breaks the proven 7/7 detection (NFR2) — reject any request to alter.
"""

# --- LOCKED calibration constants ---
SCORE_FLOOR = 0.0061   # normal_max → score 0
SCORE_CEIL = 0.0132    # luna_p80   → score 100
FIT_WINDOW = 40        # return-windows per scoring window
WINDOW_BLOCKS = 300    # blocks per activity window (~65 min)
STRIDE_BLOCKS = 100    # stride between windows
CHI = None             # bond dim: None = full rank (best); chi<4 inverts signal


def score_100(raw):
    """Map raw fragility [0,1] → calibrated score [0,100]."""
    span = SCORE_CEIL - SCORE_FLOOR
    return 100.0 * max(0.0, min(1.0, (raw - SCORE_FLOOR) / span))


def alert_level(s):
    """Fixed-threshold alert level (NFR3): RED >= 90, YELLOW >= 70, else None."""
    if s >= 90: return "RED"
    if s >= 70: return "YELLOW"
    return None
