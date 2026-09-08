"""
FAO-56 crop coefficients (Kc) for our 6 crops, plus the arid-climate
adjustment (FAO-56 Eq. 62), now driven by real Penman-Monteith ET0 and
real dew-point-derived RHmin (not the earlier mean-humidity approximation).

Source: Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998).
FAO Irrigation and Drainage Paper No. 56, Table 12.

Kc_end for maize corrected from an earlier undocumented 0.48 to 0.35 --
Table 12's actual range is 0.60 (harvested fresh, high grain moisture)
down to 0.35 (harvested field-dried). 0.35 is used here since dried/
mature harvest is the more common reference case.
"""

CROP_COEFFICIENTS = {
    "Tomato":  {"kc_ini": 0.6,  "kc_mid": 1.15, "kc_end": 0.80, "height_m": 0.6},
    "Potato":  {"kc_ini": 0.5,  "kc_mid": 1.15, "kc_end": 0.75, "height_m": 0.6},
    "Pepper,_bell": {"kc_ini": 0.6, "kc_mid": 1.05, "kc_end": 0.90, "height_m": 0.7},
    "Grape":   {"kc_ini": 0.30, "kc_mid": 0.85, "kc_end": 0.45, "height_m": 2.0},
    "Apple":   {"kc_ini": 0.60, "kc_mid": 0.95, "kc_end": 0.75, "height_m": 4.0},
    "Corn_(maize)": {"kc_ini": 0.3, "kc_mid": 1.20, "kc_end": 0.35, "height_m": 2.0},
}

# FAO-56 Eq. 62's own stated validity range -- values outside this are
# clamped, not extrapolated. When clamping occurs, the true water
# requirement is likely somewhat higher than what we report (a stated,
# honest limitation, not a bug).
RHMIN_VALID_RANGE = (20.0, 80.0)
WIND_VALID_RANGE = (1.0, 6.0)


def adjust_kc_mid(kc_mid_table, wind_speed_ms, rhmin_pct, height_m):
    """
    FAO-56 Eq. 62: adjusts baseline Kc_mid (calibrated for RHmin=45%,
    wind=2 m/s) for real local conditions. Returns (adjusted_kc, was_clamped).
    """
    u2 = min(max(wind_speed_ms, WIND_VALID_RANGE[0]), WIND_VALID_RANGE[1])
    rh_min = min(max(rhmin_pct, RHMIN_VALID_RANGE[0]), RHMIN_VALID_RANGE[1])

    was_clamped = not (RHMIN_VALID_RANGE[0] <= rhmin_pct <= RHMIN_VALID_RANGE[1]) or \
                  not (WIND_VALID_RANGE[0] <= wind_speed_ms <= WIND_VALID_RANGE[1])

    adjustment = (0.04 * (u2 - 2) - 0.004 * (rh_min - 45)) * ((height_m / 3) ** 0.3)
    return kc_mid_table + adjustment, was_clamped


def calculate_etc(et0_mm_day, crop_name, wind_speed_ms, rhmin_pct):
    """
    Returns (etc_mm_day, kc_adjusted, was_clamped) using real Penman-
    Monteith ET0 and real dew-point-derived RHmin.
    """
    if crop_name not in CROP_COEFFICIENTS:
        raise ValueError(f"Unknown crop: {crop_name}")

    coeffs = CROP_COEFFICIENTS[crop_name]
    kc_adjusted, was_clamped = adjust_kc_mid(
        coeffs["kc_mid"], wind_speed_ms, rhmin_pct, coeffs["height_m"]
    )
    etc = kc_adjusted * et0_mm_day
    return etc, kc_adjusted, was_clamped


if __name__ == "__main__":
    from nasa_power import fetch_climate_data
    from evapotranspiration import penman_monteith_et0, real_rhmin

    print("Riyadh -- ETc for all 6 crops, July (peak heat) vs January (cool):\n")
    climate, elevation = fetch_climate_data(24.71, 46.68)

    for month in ["JAN", "JUL"]:
        v = climate[month]
        et0 = penman_monteith_et0(
            temp_mean_c=v["temp_c"], temp_max_c=v["temp_max_c"], temp_min_c=v["temp_min_c"],
            dewpoint_c=v["dewpoint_c"], wind_speed_ms=v["wind_speed_ms"],
            solar_radiation_mj=v["solar_radiation_mj"], elevation_m=elevation,
            latitude_deg=24.71, month=month,
        )
        rhmin = real_rhmin(v["temp_max_c"], v["dewpoint_c"])

        print(f"--- {month} (ET0 = {et0:.2f} mm/day, RHmin = {rhmin:.1f}%) ---")
        for crop in CROP_COEFFICIENTS:
            etc, kc_adj, clamped = calculate_etc(et0, crop, v["wind_speed_ms"], rhmin)
            clamp_note = " [CLAMPED -- outside FAO-56 Eq.62 valid range, true value likely higher]" if clamped else ""
            print(f"  {crop:15s}  Kc_adj={kc_adj:.2f}  ETc={etc:.2f} mm/day{clamp_note}")
        print()