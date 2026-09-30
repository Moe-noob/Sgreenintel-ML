"""
Location- and date-specific season length, growth stages and daily water use.

1. Season and stage lengths -- FAO-56 Rev.1 (2025) method, where available
   GDD_day = min(max(Ta - Tbase, 0), Tcap - Tbase), Ta = (Tx + Tn) / 2,
   with Tbase from Rev.1 Table 6.10 and Tcap = min(Rev.1 Tupper, crop Topt
   from the Elnesr & Alazba table); each stage ends when the field-observed
   cumulative GDD of Rev.1 Table 6.11 (or the ranges of Table 6.12) is
   reached; where two rows are given (short/long season) their mean is used.
   18 of the 22 KSA crops are covered. The Topt cap was added after review:
   with Rev.1's Tupper alone, hot sowings gave unrealistically short seasons
   (spinach 29 d, broccoli 42 d, garlic 56 d); see DOCUMENTATION.md.

2. Fallback for crops not in Rev.1 Tables 6.11/6.12 (watermelon, radish,
   okra, molokhia): the Elnesr & Alazba heat-unit requirement
   HU_req = (Topt - Tbase) x DUR_total (paper Eq. 7, workbook "ThermN"),
   split over stages by the FAO-56 1998 stage shares, with the daily rate
   capped at Topt.
   Why Rev.1 first: validation/fao56rev1_gdd.py showed the Eq. 7 method
   gives seasons LONGER than Rev.1's field-observed GDD in 188 of 210 city x
   crop cases (e.g. cucumber, Makkah: 136 vs 54-90 days), because capping
   at Topt makes the 1998 durations a minimum that hot KSA sites can never
   beat. Longer seasons also overstate seasonal water.

3. Daily water use
   Kc follows FAO-56 Eq. 66 (constant ini, linear dev, constant mid, linear
   late) on the location-specific stage lengths; ETc = Kc x ET0 (Eq. 58),
   ET0 from the station's FAOCLIM-2 Penman-Monteith sinusoid.
   A dry-air upper bound applies FAO-56 Eq. 62 / 65 at RHmin = 20 %,
   u2 = 2 m/s (the lower RHmin limit of FAO-56's validity range, typical of
   inland KSA in the warm season); coastal stations sit closer to the
   central estimate.

4. Temperature stress
   For every day of the season (the spreadsheet only checks the sowing
   day): heat stress = max(0, Tmax - crTmax), cold stress = max(0,
   crTmin - Tmin), summed as degree-days, plus the count of such days.
   Degree-days weigh a 44 degC July day far more than a 36 degC one,
   which a plain day count cannot.
"""

import datetime as _dt

STAGES = ("initial", "development", "mid_season", "late_season")
MAX_SEASON_DAYS = 365
DRY_RHMIN, DRY_U2 = 20.0, 2.0


def doy_label(j):
    d = (int(round(j)) - 1) % 365
    return (_dt.date(2023, 1, 1) + _dt.timedelta(days=d)).strftime("%b %d")


def thermal_rate(ta, tb, topt):
    return min(max(ta - tb, 0.0), topt - tb)


def thermal_params(crop):
    """
    (Tbase, cap temperature, method label) used for this crop's development rate.

    For FAO-56 Rev.1 crops the cap is min(Tupper, crop Topt): Rev.1's GDD totals
    were observed mostly in climates where the mean temperature rarely exceeds
    the optimum, so Tupper there hardly bound; in Saudi heat, letting development
    keep accelerating up to Tupper (e.g. 30 degC for broccoli and garlic) gave
    unrealistic seasons (broccoli 42 d, garlic 56 d, spinach 29 d). Capping at
    the optimum is also how Elnesr & Alazba define heat units (Eq. 7).
    """
    g = crop.get("gdd_rev1")
    if g:
        cap = min(g["t_upper"], crop["t_opt"])
        return g["t_base"], cap, f"FAO-56 Rev.1 GDD ({g['source']}), capped at Topt {cap:g} degC"
    return crop["t_base"], crop["t_opt"], "heat units, Elnesr & Alazba Eq. 7 (not in FAO-56 Rev.1 GDD tables)"


def stage_requirements(crop):
    """Cumulative thermal-time targets (degC day) at the end of each stage."""
    g = crop.get("gdd_rev1")
    if g:
        cum, targets = 0.0, []
        for v in g["stages"]:
            cum += v
            targets.append(cum)
        return targets
    durs = [crop[k] for k in ("dur_ini", "dur_dev", "dur_mid", "dur_late")]
    total = sum(durs)
    cum, targets = 0.0, []
    for d in durs:
        cum += d
        targets.append(crop["hu_min_tab"] * cum / total)
    return targets


def stage_lengths(crop, station, sow_doy):
    """Location-specific (L_ini, L_dev, L_mid, L_late) or None if not completed in a year."""
    targets = stage_requirements(crop)
    tb, tcap, _ = thermal_params(crop)
    cum, bounds = 0.0, []
    for n in range(MAX_SEASON_DAYS):
        cum += thermal_rate(station.ta(sow_doy + n), tb, tcap)
        while len(bounds) < 4 and cum >= targets[len(bounds)] - 1e-9:
            bounds.append(n + 1)
        if len(bounds) == 4:
            break
    if len(bounds) < 4:
        return None
    lengths = (bounds[0], bounds[1] - bounds[0], bounds[2] - bounds[1], bounds[3] - bounds[2])
    # A stage that completes on the same day as the previous one would have
    # zero length; FAO-56 Eq. 66 needs >= 1 day per stage.
    return tuple(max(1, x) for x in lengths)


def kc_on_day(i, lengths, kc_ini, kc_mid, kc_end):
    """FAO-56 Eq. 66; i is 0-based day in season."""
    l_ini, l_dev, l_mid, l_late = lengths
    d = i + 1
    if d <= l_ini:
        return kc_ini
    if d <= l_ini + l_dev:
        return kc_ini + (d - l_ini) / l_dev * (kc_mid - kc_ini)
    if d <= l_ini + l_dev + l_mid:
        return kc_mid
    return kc_mid + (d - l_ini - l_dev - l_mid) / l_late * (kc_end - kc_mid)


def adjust_kc(kc_table, height_m, u2=DRY_U2, rhmin=DRY_RHMIN, apply=True):
    """FAO-56 Eq. 62 (Kc_mid) / Eq. 65 (Kc_end, only when Kc_end >= 0.45), inputs clamped to FAO-56's valid ranges.
    Defaults give the dry-air upper bound (RHmin 20 %, u2 2 m/s)."""
    if not apply:
        return kc_table
    h = min(max(height_m, 0.1), 10.0)
    u2 = min(max(u2, 1.0), 6.0)
    rhmin = min(max(rhmin, 20.0), 80.0)
    return kc_table + (0.04 * (u2 - 2) - 0.004 * (rhmin - 45)) * (h / 3) ** 0.3


def simulate(crop, station, sow_doy, detail=False):
    lengths = stage_lengths(crop, station, sow_doy)
    if lengths is None:
        return {"sow_doy": sow_doy, "viable": False, "reason": "thermal-time requirement not met within 365 days"}
    total = sum(lengths)
    kc_mid_hi = adjust_kc(crop["kc_mid"], crop["height_m"])
    kc_end_hi = adjust_kc(crop["kc_end"], crop["height_m"], apply=crop["kc_end"] >= 0.45)
    bounds = [0, lengths[0], lengths[0] + lengths[1], lengths[0] + lengths[1] + lengths[2], total]

    etc = [0.0] * 4
    etc_hi = [0.0] * 4
    et0s = [0.0] * 4
    heat = [0] * 4
    cold = [0] * 4
    heat_dd = [0.0] * 4
    cold_dd = [0.0] * 4
    daily = [] if detail else None
    peak = (0.0, None)
    for n in range(total):
        j = sow_doy + n
        s = 0 if n < bounds[1] else 1 if n < bounds[2] else 2 if n < bounds[3] else 3
        kc = kc_on_day(n, lengths, crop["kc_ini"], crop["kc_mid"], crop["kc_end"])
        kc_hi = kc_on_day(n, lengths, crop["kc_ini"], kc_mid_hi, kc_end_hi)
        e0 = station.et0(j)
        etc[s] += kc * e0
        etc_hi[s] += kc_hi * e0
        et0s[s] += e0
        tx, tn = station.tx(j), station.tn(j)
        if tx > crop["t_max"]:
            heat[s] += 1
            heat_dd[s] += tx - crop["t_max"]
        if tn < crop["t_min"]:
            cold[s] += 1
            cold_dd[s] += crop["t_min"] - tn
        if kc * e0 > peak[0]:
            peak = (kc * e0, j)
        if detail:
            daily.append({"day": n + 1, "doy": ((j - 1) % 365) + 1, "date": doy_label(j), "stage": STAGES[s],
                          "tx": tx, "tn": tn, "et0": e0, "kc": kc, "etc": kc * e0, "etc_hi": kc_hi * e0})

    stages = []
    for s, name in enumerate(STAGES):
        a, b = bounds[s], bounds[s + 1]
        stages.append({"stage": name, "days": b - a, "start": doy_label(sow_doy + a), "end": doy_label(sow_doy + b - 1),
                       "et0_mm": et0s[s], "etc_mm": etc[s], "etc_hi_mm": etc_hi[s],
                       "etc_mm_day": etc[s] / (b - a), "heat_days": heat[s], "cold_days": cold[s],
                       "heat_dd": heat_dd[s], "cold_dd": cold_dd[s]})
    out = {
        "sow_doy": sow_doy, "sow_date": doy_label(sow_doy), "harvest_date": doy_label(sow_doy + total - 1),
        "viable": True, "stage_lengths": lengths, "total_days": total, "stages": stages,
        "season_et0_mm": sum(et0s), "season_etc_mm": sum(etc), "season_etc_hi_mm": sum(etc_hi),
        "mean_etc_mm_day": sum(etc) / total, "peak_etc_mm_day": peak[0], "peak_date": doy_label(peak[1]),
        "heat_days": sum(heat), "cold_days": sum(cold),
        "heat_dd": sum(heat_dd), "cold_dd": sum(cold_dd), "stress_dd": sum(heat_dd) + sum(cold_dd),
        "length_method": thermal_params(crop)[2],
    }
    if detail:
        out["daily"] = daily
    return out
