"""
Reference evapotranspiration (ET0).

Primary method: FAO-56 Penman-Monteith (Eq. 6) -- the international
standard, uses temperature, humidity, wind, and radiation. Requires
more inputs than Hargreaves but is meaningfully more accurate,
especially in extreme arid conditions like Saudi Arabia's (per FAO-56's
own documented ~30% typical divergence in dry climates).

Secondary method: Hargreaves-Samani -- kept for comparison/reporting,
since it was our original method and the gap between the two is itself
a useful, citable finding.

All equation numbers reference: Allen, R.G., Pereira, L.S., Raes, D.,
Smith, M. (1998). FAO Irrigation and Drainage Paper No. 56, Chapter 3.
"""

import math

MID_MONTH_DAY = {
    "JAN": 15, "FEB": 46, "MAR": 74, "APR": 105, "MAY": 135, "JUN": 166,
    "JUL": 196, "AUG": 227, "SEP": 258, "OCT": 288, "NOV": 319, "DEC": 349,
}


def saturation_vapor_pressure(temp_c):
    """e°(T), FAO-56 Eq. 11 -- saturation vapor pressure at a given temperature."""
    return 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))


def slope_vapor_pressure_curve(temp_c):
    """Delta, FAO-56 Eq. 13."""
    es = saturation_vapor_pressure(temp_c)
    return (4098 * es) / ((temp_c + 237.3) ** 2)


def atmospheric_pressure(elevation_m):
    """P, FAO-56 Eq. 7 -- atmospheric pressure decreases with elevation."""
    return 101.3 * (((293 - 0.0065 * elevation_m) / 293) ** 5.26)


def psychrometric_constant(elevation_m):
    """Gamma, FAO-56 Eq. 8."""
    return 0.000665 * atmospheric_pressure(elevation_m)


def extraterrestrial_radiation(latitude_deg, day_of_year):
    """Ra, FAO-56 Eq. 21-25 -- same as before, unchanged."""
    lat_rad = math.radians(latitude_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * day_of_year / 365)
    delta = 0.409 * math.sin(2 * math.pi * day_of_year / 365 - 1.39)
    ws = math.acos(-math.tan(lat_rad) * math.tan(delta))
    Gsc = 0.0820
    Ra_MJ = (24 * 60 / math.pi) * Gsc * dr * (
        ws * math.sin(lat_rad) * math.sin(delta) +
        math.cos(lat_rad) * math.cos(delta) * math.sin(ws)
    )
    return Ra_MJ  # MJ/m2/day (kept in energy units here, unlike the old mm-converted version)


def clear_sky_radiation(ra, elevation_m):
    """Rso, FAO-56 Eq. 37."""
    return (0.75 + 2e-5 * elevation_m) * ra


def net_radiation(temp_max_c, temp_min_c, solar_radiation_mj, ea, ra, elevation_m):
    """Rn = Rns - Rnl, FAO-56 Eq. 38-39."""
    albedo = 0.23  # reference crop albedo, FAO-56 standard value
    rns = (1 - albedo) * solar_radiation_mj  # Eq. 38

    rso = clear_sky_radiation(ra, elevation_m)
    sigma = 4.903e-9  # Stefan-Boltzmann constant, MJ K^-4 m^-2 day^-1

    tmax_k = temp_max_c + 273.16
    tmin_k = temp_min_c + 273.16

    rs_rso_ratio = min(solar_radiation_mj / rso, 1.0) if rso > 0 else 1.0  # physically capped at 1.0

    rnl = sigma * ((tmax_k ** 4 + tmin_k ** 4) / 2) * (0.34 - 0.14 * math.sqrt(max(ea, 0))) * (1.35 * rs_rso_ratio - 0.35)  # Eq. 39

    return rns - rnl


def penman_monteith_et0_doy(temp_mean_c, temp_max_c, temp_min_c, dewpoint_c,
                              wind_speed_ms, solar_radiation_mj, elevation_m,
                              latitude_deg, day_of_year, soil_heat_flux_mj=0.0):
    """
    FAO-56 Penman-Monteith reference evapotranspiration, Eq. 6, for a
    given day of year. Returns ET0 in mm/day.

    Soil heat flux G: FAO-56 states G may be ignored (G ~ 0) for DAILY and
    ten-day periods (Eq. 42). For MONTHLY periods FAO-56 gives
    Eq. 43, G = 0.07 (T_month,i+1 - T_month,i-1); the monthly wrapper below
    passes that in. (The earlier comment claiming FAO-56 says G is
    negligible at monthly resolution was wrong; the effect is small --
    ~0.04 mm/day in FAO-56 Example 18 -- but the citation now matches.)

    Validated against FAO-56 Example 18 (Bangkok, April): 5.72 mm/day.
    """
    delta = slope_vapor_pressure_curve(temp_mean_c)
    gamma = psychrometric_constant(elevation_m)

    es_max = saturation_vapor_pressure(temp_max_c)
    es_min = saturation_vapor_pressure(temp_min_c)
    es = (es_max + es_min) / 2  # Eq. 12

    ea = saturation_vapor_pressure(dewpoint_c)  # Eq. 14 -- actual vapor pressure from dew point

    ra = extraterrestrial_radiation(latitude_deg, day_of_year)
    rn = net_radiation(temp_max_c, temp_min_c, solar_radiation_mj, ea, ra, elevation_m)

    G = soil_heat_flux_mj

    numerator = (0.408 * delta * (rn - G)) + (gamma * (900 / (temp_mean_c + 273)) * wind_speed_ms * (es - ea))
    denominator = delta + gamma * (1 + 0.34 * wind_speed_ms)

    et0 = numerator / denominator
    return max(et0, 0)  # ET0 can't be physically negative


def penman_monteith_et0(temp_mean_c, temp_max_c, temp_min_c, dewpoint_c,
                        wind_speed_ms, solar_radiation_mj, elevation_m,
                        latitude_deg, month, soil_heat_flux_mj=0.0):
    """
    Monthly wrapper (mid-month day of year). Pass soil_heat_flux_mj from
    FAO-56 Eq. 43 if the neighbouring months' mean temperatures are
    available; defaults to 0 (small, documented approximation).
    """
    return penman_monteith_et0_doy(
        temp_mean_c, temp_max_c, temp_min_c, dewpoint_c, wind_speed_ms,
        solar_radiation_mj, elevation_m, latitude_deg, MID_MONTH_DAY[month],
        soil_heat_flux_mj=soil_heat_flux_mj,
    )


def monthly_soil_heat_flux(t_next_month_c, t_prev_month_c):
    """FAO-56 Eq. 43: G for a monthly period, MJ m-2 day-1."""
    return 0.07 * (t_next_month_c - t_prev_month_c)


def real_rhmin(temp_max_c, dewpoint_c):
    """
    Approximates the day's minimum relative humidity (occurs near the
    time of maximum temperature) using actual vapor pressure (from dew
    point) against saturation vapor pressure at Tmax. This replaces our
    earlier use of mean humidity as a stand-in for RHmin.
    """
    ea = saturation_vapor_pressure(dewpoint_c)
    es_tmax = saturation_vapor_pressure(temp_max_c)
    return min(max((ea / es_tmax) * 100, 0), 100)


def hargreaves_et0_doy(temp_mean_c, temp_max_c, temp_min_c, latitude_deg, day_of_year):
    """
    Hargreaves-Samani reference evapotranspiration for a specific day of
    year. Temperature-only method -- no humidity, wind, or solar
    radiation input required (Ra is computed purely from latitude and
    day-of-year via extraterrestrial_radiation()).

    Kept as a fallback if Open-Meteo (used for care/tracker.py's live
    ETc) is ever unreachable -- not used in the primary live-ETc path,
    since FAO-56 documents this method can diverge from Penman-Monteith
    by up to ~30% in extreme arid conditions (confirmed for Riyadh:
    -22% to -34% across all 12 months in this file's own self-test).
    """
    ra_mj = extraterrestrial_radiation(latitude_deg, day_of_year)
    ra_mm = 0.408 * ra_mj  # convert energy units to mm/day equivalent

    temp_range = temp_max_c - temp_min_c
    if temp_range < 0:
        raise ValueError(f"temp_max ({temp_max_c}) is less than temp_min ({temp_min_c})")

    return 0.0023 * (temp_mean_c + 17.8) * (temp_range ** 0.5) * ra_mm


def hargreaves_et0(temp_mean_c, temp_max_c, temp_min_c, latitude_deg, month):
    """Monthly wrapper (mid-month day of year). Kept for comparison
    against Penman-Monteith in the monthly climatology self-test below."""
    return hargreaves_et0_doy(
        temp_mean_c, temp_max_c, temp_min_c, latitude_deg, MID_MONTH_DAY[month]
    )


def wind_speed_2m(wind_speed_10m_ms):
    """
    FAO-56 Eq.47 -- converts wind speed measured at 10m height (Open-
    Meteo's standard) to the 2m height Penman-Monteith requires.
    NASA POWER's AG-community WS2M is already at 2m and needs no
    conversion; this is only for sources reporting at 10m.
    """
    return wind_speed_10m_ms * 4.87 / math.log(67.8 * 10 - 5.42)


if __name__ == "__main__":
    from nasa_power import fetch_climate_data

    print("Riyadh -- Penman-Monteith vs Hargreaves, all 12 months:\n")
    climate, elevation = fetch_climate_data(24.71, 46.68)

    for month, v in climate.items():
        et0_pm = penman_monteith_et0(
            temp_mean_c=v["temp_c"], temp_max_c=v["temp_max_c"], temp_min_c=v["temp_min_c"],
            dewpoint_c=v["dewpoint_c"], wind_speed_ms=v["wind_speed_ms"],
            solar_radiation_mj=v["solar_radiation_mj"], elevation_m=elevation,
            latitude_deg=24.71, month=month,
        )
        et0_hs = hargreaves_et0(
            temp_mean_c=v["temp_c"], temp_max_c=v["temp_max_c"], temp_min_c=v["temp_min_c"],
            latitude_deg=24.71, month=month,
        )
        rhmin = real_rhmin(v["temp_max_c"], v["dewpoint_c"])
        diff_pct = ((et0_hs - et0_pm) / et0_pm) * 100

        print(f"  {month}: ET0_PM={et0_pm:.2f}  ET0_HS={et0_hs:.2f}  diff={diff_pct:+.1f}%  RHmin={rhmin:.1f}%")