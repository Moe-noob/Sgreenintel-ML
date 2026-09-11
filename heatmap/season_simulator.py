"""
Planting-date simulator.

For an ANNUAL crop, every candidate planting day is simulated through its
whole growth cycle on the local daily climatology:

  1. Stage lengths come from cumulative growing degree days (GDD), the
     FAO56rev method (Paredes et al. 2025, Eq. 1 and Tables 5/6): the
     crop moves from initial -> development -> mid-season -> late season
     when it has accumulated the tabulated GDD for each stage. Stage
     lengths therefore differ by location and planting date, which is
     exactly what a fixed calendar cannot do.
  2. Kc follows the FAO-56 segmented curve (Eq. 66) between Kc_ini,
     Kc_mid and Kc_end, with Kc_mid / Kc_end climate-adjusted for the
     actual RHmin and wind of the mid and late stages (Eq. 62 / Eq. 65).
  3. ET0 is FAO-56 Penman-Monteith (Eq. 6) on each day of the cycle;
     ETc = Kc * ET0 (Eq. 58); water is summed per stage and per season.
  4. Selection follows Elnesr & Alazba (2016, King Saud University):
       (a) the crop must complete its heat-unit (GDD) requirement --
           here: within one year, else the date is rejected;
       (b) heat / cold shocks are counted and used to flag dates
           (they warn, they do not reject);
       (c) among dates passing (a), prefer shock-free dates, and choose
           the one with the MINIMUM seasonal ETc.
     Shock test (Elnesr & Alazba 2016, Sec. 2.4.1): a day is a heat shock
     if Tmax > crop maximum tolerable temperature (Txc) and a cold shock
     if Tmin < crop minimum tolerable temperature (Tnc). "Shock-free"
     means zero days of either kind. Two further counts are reported for
     transparency (they are NOT part of the shock test):
       heat-ceiling day: Tavg > Tupper  (no further GDD accumulation)
       cold day:         Tavg < Tbase   (zero GDD)
     No weighted score is used; every reported number is a direct
     count, sum, or tabulated value.

For a PERENNIAL crop (Grape, Apple) a single annual cycle of an
established plant is computed with FAO-56 Table 11 stage lengths.
"""

import datetime as _dt

from evapotranspiration import penman_monteith_et0_doy, real_rhmin
from crop_coefficients import adjust_kc_mid, adjust_kc_end, kc_on_day
from crop_database import CROP_DB, growing_degree_day

STAGES = ("initial", "development", "mid_season", "late_season")


def raw_year_exceedances(raw_years, start_doy, total_days, txc, tnc):
    """
    Count, for each observed year, the days in [start_doy, start_doy+total_days)
    with Tmax > Txc and with Tmin < Tnc, using the UNSMOOTHED daily record.
    A season that wraps past 31 Dec continues into the next observed year;
    years whose season cannot be completed from the record are skipped.
    Returns dict with per-year lists and mean/min/max, or None if no data.
    """
    if not raw_years or txc is None or tnc is None:
        return None
    years = sorted(raw_years)
    heat, cold, used = [], [], []
    for y in years:
        h = c = 0
        ok = True
        for n in range(total_days):
            idx = int(start_doy) - 1 + n
            yr = y
            if idx >= 365:
                idx -= 365
                yr = str(int(y) + 1)
                if yr not in raw_years:
                    ok = False
                    break
            tmax = raw_years[yr]["temp_max_c"][idx]
            tmin = raw_years[yr]["temp_min_c"][idx]
            if tmax is not None and tmax > txc:
                h += 1
            if tmin is not None and tmin < tnc:
                c += 1
        if ok:
            heat.append(h); cold.append(c); used.append(y)
    if not used:
        return None
    return {"years": used, "heat_per_year": heat, "cold_per_year": cold,
            "heat_mean": sum(heat) / len(heat), "heat_min": min(heat), "heat_max": max(heat),
            "cold_mean": sum(cold) / len(cold), "cold_min": min(cold), "cold_max": max(cold)}
MAX_SEASON_DAYS = 365


def doy_to_date(doy):
    """Day-of-year (1..365, cyclic) -> 'Mon DD' using a non-leap reference year."""
    d = (int(doy) - 1) % 365
    return (_dt.date(2023, 1, 1) + _dt.timedelta(days=d)).strftime("%b %d")


def _day(clim, doy):
    return clim[(int(doy) - 1) % 365]


def _et0_for(clim_day, elevation_m, latitude_deg):
    return penman_monteith_et0_doy(
        clim_day["temp_c"], clim_day["temp_max_c"], clim_day["temp_min_c"],
        clim_day["dewpoint_c"], clim_day["wind_speed_ms"], clim_day["solar_radiation_mj"],
        elevation_m, latitude_deg, clim_day["doy"],
    )


def _stage_lengths_from_gdd(crop, clim, planting_doy):
    """Walk forward from planting day accumulating GDD; return stage lengths or None."""
    g = crop["gdd_stages"]
    targets = [g["ini"], g["ini"] + g["dev"], g["ini"] + g["dev"] + g["mid"],
               g["ini"] + g["dev"] + g["mid"] + g["late"]]
    cum = 0.0
    boundaries = []
    for n in range(MAX_SEASON_DAYS):
        d = _day(clim, planting_doy + n)
        cum += growing_degree_day(d["temp_max_c"], d["temp_min_c"], crop["t_base"], crop["t_upper"])
        while len(boundaries) < 4 and cum >= targets[len(boundaries)]:
            boundaries.append(n + 1)      # stage ends after day n+1
        if len(boundaries) == 4:
            break
    if len(boundaries) < 4:
        return None
    return (boundaries[0], boundaries[1] - boundaries[0],
            boundaries[2] - boundaries[1], boundaries[3] - boundaries[2])


def _run_cycle(crop, clim, elevation_m, latitude_deg, start_doy, stage_lengths, raw_years=None):
    """Shared daily loop for annuals and perennials."""
    l_ini, l_dev, l_mid, l_late = stage_lengths
    total_days = sum(stage_lengths)
    mid_start, late_start = l_ini + l_dev, l_ini + l_dev + l_mid

    # Climate averages for the Kc adjustments (FAO-56: averages over mid and late stages)
    def _avg(field_fn, a, b):
        return sum(field_fn(_day(clim, start_doy + n)) for n in range(a, b)) / max(b - a, 1)
    rh_fn = lambda d: real_rhmin(d["temp_max_c"], d["dewpoint_c"])
    u2_fn = lambda d: d["wind_speed_ms"]
    kc_mid_adj, note_mid = adjust_kc_mid(crop["kc_mid"], _avg(u2_fn, mid_start, late_start),
                                         _avg(rh_fn, mid_start, late_start), crop["height_m"])
    kc_end_adj, note_end = adjust_kc_end(crop["kc_end"], _avg(u2_fn, late_start, total_days),
                                         _avg(rh_fn, late_start, total_days), crop["height_m"])

    stage_of = lambda n: 0 if n < l_ini else 1 if n < mid_start else 2 if n < late_start else 3
    etc_by_stage = [0.0, 0.0, 0.0, 0.0]
    et0_total = 0.0
    heat_ceiling_days = cold_days = 0
    heat_shock_days = cold_shock_days = 0
    txc, tnc = crop.get("t_max_tolerable"), crop.get("t_min_tolerable")
    peak_etc, peak_doy = 0.0, None

    for n in range(total_days):
        d = _day(clim, start_doy + n)
        kc = kc_on_day(n, stage_lengths, crop["kc_ini"], kc_mid_adj, kc_end_adj)
        et0 = _et0_for(d, elevation_m, latitude_deg)
        etc = kc * et0
        etc_by_stage[stage_of(n)] += etc
        et0_total += et0
        t_avg = (d["temp_max_c"] + d["temp_min_c"]) / 2
        if t_avg > crop["t_upper"]:
            heat_ceiling_days += 1
        if t_avg < crop["t_base"]:
            cold_days += 1
        if txc is not None and d["temp_max_c"] > txc:
            heat_shock_days += 1
        if tnc is not None and d["temp_min_c"] < tnc:
            cold_shock_days += 1
        if etc > peak_etc:
            peak_etc, peak_doy = etc, d["doy"]

    stages = []
    for i, name in enumerate(STAGES):
        s_start = sum(stage_lengths[:i])
        stages.append({
            "stage": name,
            "days": stage_lengths[i],
            "start": doy_to_date(start_doy + s_start),
            "end": doy_to_date(start_doy + s_start + stage_lengths[i] - 1),
            "etc_mm": etc_by_stage[i],
            "etc_mm_per_day": etc_by_stage[i] / stage_lengths[i],
        })

    return {
        "start_doy": start_doy, "start_date": doy_to_date(start_doy),
        "end_date": doy_to_date(start_doy + total_days - 1),
        "total_days": total_days, "stage_lengths": stage_lengths, "stages": stages,
        "kc_mid_adjusted": kc_mid_adj, "kc_end_adjusted": kc_end_adj,
        "kc_clamp_note": note_mid or note_end,
        "seasonal_et0_mm": et0_total, "seasonal_etc_mm": sum(etc_by_stage),
        "seasonal_m3_per_ha": sum(etc_by_stage) * 10,     # 1 mm over 1 ha = 10 m3
        "peak_etc_mm_day": peak_etc, "peak_date": doy_to_date(peak_doy) if peak_doy else None,
        "heat_ceiling_days": heat_ceiling_days, "cold_days": cold_days,
        "heat_shock_days": heat_shock_days, "cold_shock_days": cold_shock_days,
        "shock_test_applied": txc is not None and tnc is not None,
        "shock_free": heat_shock_days == 0 and cold_shock_days == 0,
        # Observed-year statistics from the unsmoothed 2014-2023 record
        # (reported; selection uses the climatology counts above, as in Elnesr & Alazba's sinusoidal climatology)
        "raw_exceedances": raw_year_exceedances(raw_years, start_doy, total_days, txc, tnc),
    }


def simulate_annual_season(crop_name, clim, elevation_m, latitude_deg, planting_doy, raw_years=None):
    crop = CROP_DB[crop_name]
    stage_lengths = _stage_lengths_from_gdd(crop, clim, planting_doy)
    if stage_lengths is None:
        return {"start_doy": planting_doy, "start_date": doy_to_date(planting_doy),
                "viable": False, "reason": "GDD requirement not reached within one year"}
    result = _run_cycle(crop, clim, elevation_m, latitude_deg, planting_doy, stage_lengths, raw_years)
    result["viable"] = True
    result["crop"] = crop_name
    return result


def scan_planting_dates(crop_name, clim, elevation_m, latitude_deg, step_days=10, raw_years=None):
    """
    Simulate every candidate planting day; return all runs plus the
    selection per Elnesr & Alazba (2016): viable -> prefer shock-free ->
    minimum seasonal ETc.
    """
    runs = [simulate_annual_season(crop_name, clim, elevation_m, latitude_deg, doy, raw_years)
            for doy in range(1, 366, step_days)]
    viable = [r for r in runs if r["viable"]]
    shock_free = [r for r in viable if r["shock_free"]]
    # Selection follows the Elnesr & Alazba (2016, Sec. 2.4.1) sequence:
    # heat units met -> prefer dates without tolerance exceedances -> choose
    # by water. Their rule minimises TOTAL seasonal ETc over a FIXED season
    # length per crop. Our season lengths vary with GDD, so total ETc would
    # reward short, hot seasons; this implementation therefore minimises
    # MEAN DAILY ETc. That is an ADAPTATION of their rule, not a literal
    # reproduction, and both seasonal and mean-daily ETc are reported so the
    # choice is visible. Exceedance days on the chosen date are reported as
    # warnings, as in their model (they warn, they do not reject).
    pool = shock_free if shock_free else viable
    best = min(pool, key=lambda r: r["seasonal_etc_mm"] / r["total_days"]) if pool else None
    if best is None:
        basis = "no viable planting date"
    elif shock_free:
        basis = "lowest mean daily ETc among dates with no tolerance exceedances (adapted from Elnesr & Alazba 2016)"
    else:
        basis = "no exceedance-free date exists; least-water viable candidate by mean daily ETc; exceedance days reported as a warning"
    return {
        "crop": crop_name, "step_days": step_days, "runs": runs,
        "n_candidates": len(runs), "n_viable": len(viable), "n_shock_free": len(shock_free),
        "shock_free_dates": [r["start_date"] for r in shock_free],
        "best": best, "selection_basis": basis,
    }


def simulate_perennial_cycle(crop_name, clim, elevation_m, latitude_deg):
    crop = CROP_DB[crop_name]
    cyc = crop["annual_cycle"]
    start_doy = _dt.date(2023, cyc["start_month"], 1).timetuple().tm_yday
    result = _run_cycle(crop, clim, elevation_m, latitude_deg, start_doy, cyc["stage_days"])
    result.update({"crop": crop_name, "viable": True, "stage_source": cyc["source"],
                   "establishment_note": crop["establishment_note"],
                   "suitability_status": crop.get("suitability_status", "established-plant estimate"),
                   "suitability_reason": crop.get("suitability_reason", "")})
    return result


def contiguous_windows(dates_doy, step_days):
    """Group candidate planting DOYs into contiguous windows (cyclic over the year)."""
    if not dates_doy:
        return []
    s = sorted(dates_doy)
    windows, cur = [], [s[0]]
    for d in s[1:]:
        if d - cur[-1] <= step_days:
            cur.append(d)
        else:
            windows.append(cur)
            cur = [d]
    windows.append(cur)
    # merge Dec->Jan wrap
    if len(windows) > 1 and (365 - windows[-1][-1]) + windows[0][0] <= step_days:
        windows[0] = windows[-1] + windows[0]
        windows.pop()
    return [(doy_to_date(w[0]), doy_to_date(w[-1])) for w in windows]