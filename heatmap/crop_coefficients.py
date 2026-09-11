"""
FAO-56 crop-coefficient machinery.

Kc values themselves now live in crop_database.py (single source of
truth); this module keeps the calculation functions:

  adjust_kc_mid  -- FAO-56 Eq. 62 (validated against Example 27: 1.30 / 1.07)
  adjust_kc_end  -- FAO-56 Eq. 65 (same form; applied only when Kc_end >= 0.45)
  kc_on_day      -- FAO-56 Eq. 66, the segmented Kc curve
  calculate_etc  -- legacy helper (flat Kc_mid), kept for old callers

Table 12 values are for RHmin ~ 45 % and u2 ~ 2 m/s. Both adjustments
are restricted to FAO-56's stated validity ranges (RHmin 20-80 %,
u2 1-6 m/s, h 0.1-10 m); inputs outside are clamped and flagged. When
RHmin is clamped UP to 20 % (common inland KSA) or u2 clamped DOWN to
6 m/s, the true Kc is somewhat HIGHER than reported; when u2 is clamped
UP to 1 m/s the true Kc is somewhat LOWER. The flag reports which.
"""

from crop_database import CROP_COEFFICIENTS  # noqa: F401  (re-exported for old imports)

RHMIN_VALID_RANGE = (20.0, 80.0)
WIND_VALID_RANGE = (1.0, 6.0)
HEIGHT_VALID_RANGE = (0.1, 10.0)


def _clamp_inputs(wind_speed_ms, rhmin_pct, height_m):
    u2 = min(max(wind_speed_ms, WIND_VALID_RANGE[0]), WIND_VALID_RANGE[1])
    rh = min(max(rhmin_pct, RHMIN_VALID_RANGE[0]), RHMIN_VALID_RANGE[1])
    h = min(max(height_m, HEIGHT_VALID_RANGE[0]), HEIGHT_VALID_RANGE[1])
    direction = None
    if rhmin_pct < RHMIN_VALID_RANGE[0] or wind_speed_ms > WIND_VALID_RANGE[1]:
        direction = "true Kc likely higher"
    elif wind_speed_ms < WIND_VALID_RANGE[0]:
        direction = "true Kc likely lower"
    return u2, rh, h, direction


def adjust_kc_mid(kc_mid_table, wind_speed_ms, rhmin_pct, height_m):
    """FAO-56 Eq. 62. Returns (adjusted_kc, clamp_note_or_None)."""
    u2, rh, h, note = _clamp_inputs(wind_speed_ms, rhmin_pct, height_m)
    adj = (0.04 * (u2 - 2) - 0.004 * (rh - 45)) * ((h / 3) ** 0.3)
    return kc_mid_table + adj, note


def adjust_kc_end(kc_end_table, wind_speed_ms, rhmin_pct, height_m):
    """FAO-56 Eq. 65. Only applied when tabulated Kc_end >= 0.45."""
    if kc_end_table < 0.45:
        return kc_end_table, None
    u2, rh, h, note = _clamp_inputs(wind_speed_ms, rhmin_pct, height_m)
    adj = (0.04 * (u2 - 2) - 0.004 * (rh - 45)) * ((h / 3) ** 0.3)
    return kc_end_table + adj, note


def kc_on_day(day_index, stage_lengths, kc_ini, kc_mid, kc_end):
    """
    FAO-56 Eq. 66. day_index is 0-based day within the season;
    stage_lengths = (L_ini, L_dev, L_mid, L_late) in days.
    Constant in initial and mid stages, linear in development and late.
    Validated against FAO-56 Example 28.
    """
    l_ini, l_dev, l_mid, l_late = stage_lengths
    i = day_index + 1  # FAO counts days from 1
    if i <= l_ini:
        return kc_ini
    if i <= l_ini + l_dev:
        return kc_ini + ((i - l_ini) / l_dev) * (kc_mid - kc_ini)
    if i <= l_ini + l_dev + l_mid:
        return kc_mid
    prev = l_ini + l_dev + l_mid
    return kc_mid + ((i - prev) / l_late) * (kc_end - kc_mid)


def calculate_etc(et0_mm_day, crop_name, wind_speed_ms, rhmin_pct):
    """Legacy: ETc with flat climate-adjusted Kc_mid. Returns (etc, kc_adj, was_clamped)."""
    if crop_name not in CROP_COEFFICIENTS:
        raise ValueError(f"Unknown crop: {crop_name}")
    c = CROP_COEFFICIENTS[crop_name]
    kc_adj, note = adjust_kc_mid(c["kc_mid"], wind_speed_ms, rhmin_pct, c["height_m"])
    return kc_adj * et0_mm_day, kc_adj, note is not None


if __name__ == "__main__":
    # FAO-56 Example 27 and Example 28 self-tests
    print("Eq.62 Mocha :", round(adjust_kc_mid(1.20, 4.6, 44, 2.0)[0], 2), "(expect 1.30)")
    print("Eq.62 Taipei:", round(adjust_kc_mid(1.20, 1.3, 75, 2.0)[0], 2), "(expect 1.07)")
    st = (25, 25, 30, 20)
    for d, exp in [(20, 0.15), (40, 0.77), (70, 1.19), (95, 0.56)]:
        print(f"Eq.66 day {d}: {kc_on_day(d - 1, st, 0.15, 1.19, 0.35):.2f} (expect {exp})")
