"""
From crop water use (ETc) to an irrigation plan a farmer can follow.

  net irrigation   = ETc   (effective rainfall is ignored -- conservative;
                            most of KSA gets < 100 mm/yr, mostly in winter)
  gross irrigation = net / (Ea * (1 - LR))
      Ea = field application efficiency of the system   [FAO-TM4]
      LR = leaching requirement for the water's salinity [FAO29]
  Irrigation interval per stage (FAO-56 Ch. 8):
      TAW = 1000 (theta_FC - theta_WP) Zr          [mm]
      RAW = p TAW, p adjusted for ETc              [mm]
      max interval = RAW / ETc                     [days]
  Zr grows linearly from 0.20 m at sowing to the crop's Zr at the start of
  mid-season, then stays constant.

For drip, the interval is the MAXIMUM allowed before stress; drip systems
in practice run daily or every other day with a correspondingly smaller
depth. The seasonal and monthly volumes are what matter for planning.
"""

import datetime as _dt

from agronomy import (IRRIGATION_EFFICIENCY, ROOTING, SOILS, ZR_INITIAL_M,
                      adjusted_p, leaching_requirement, salinity_yield_pct, SALT_TOLERANCE)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _root_depth(day, lengths, zr_max):
    grow_days = lengths[0] + lengths[1]
    if day >= grow_days:
        return zr_max
    z0 = min(ZR_INITIAL_M, zr_max)
    return z0 + (zr_max - z0) * day / max(grow_days, 1)


def plan(crop, sim, soil="loamy_sand", method="drip", ecw_ds_m=None, spacing_m=None):
    """
    crop: KSA crop row; sim: season.simulate(..., detail=True)
    soil: key of agronomy.SOILS; method: drip | sprinkler | surface
    ecw_ds_m: irrigation water salinity (dS/m), None = fresh water
    spacing_m: (row spacing, in-row spacing) in metres, for per-plant litres
    """
    ea = IRRIGATION_EFFICIENCY[method]
    lr, lr_note = leaching_requirement(crop["key"], ecw_ds_m, method)
    notes = [lr_note] if lr_note else []
    if lr is None:
        lr = 0.0
        notes.append("gross figures below exclude leaching")
    gross_factor = 1.0 / (ea * (1.0 - lr))
    theta_fc, theta_wp = SOILS[soil]
    rooting = ROOTING.get(crop["key"])
    area_per_plant = spacing_m[0] * spacing_m[1] if spacing_m else None

    stages, day0 = [], 0
    for st in sim["stages"]:
        mid_day = day0 + st["days"] / 2
        row = {**st, "etc_m3_ha": st["etc_mm"] * 10, "gross_mm": st["etc_mm"] * gross_factor,
               "gross_m3_ha": st["etc_mm"] * gross_factor * 10}
        if rooting:
            zr = _root_depth(mid_day, sim["stage_lengths"], rooting[0])
            taw = 1000 * (theta_fc - theta_wp) * zr
            p = adjusted_p(rooting[2], st["etc_mm_day"])
            raw = p * taw
            row.update({"root_depth_m": zr, "taw_mm": taw, "p": p, "raw_mm": raw,
                        "max_interval_days": max(1, int(raw / st["etc_mm_day"])) if st["etc_mm_day"] > 0 else None,
                        "net_per_event_mm": raw, "gross_per_event_mm": raw * gross_factor})
        if area_per_plant:
            row["l_per_plant_day"] = st["etc_mm_day"] * area_per_plant
            row["gross_l_per_plant_day"] = st["etc_mm_day"] * area_per_plant * gross_factor
        stages.append(row)
        day0 += st["days"]
    if not rooting:
        notes.append("no FAO-56 Table 22 rooting depth for this crop; irrigation interval not computed")

    monthly = {}
    for d in sim["daily"]:
        m = MONTHS[(_dt.date(2023, 1, 1) + _dt.timedelta(days=d["doy"] - 1)).month - 1]
        e = monthly.setdefault(m, {"days": 0, "etc_mm": 0.0})
        e["days"] += 1
        e["etc_mm"] += d["etc"]
    order = []
    for d in sim["daily"]:
        m = MONTHS[(_dt.date(2023, 1, 1) + _dt.timedelta(days=d["doy"] - 1)).month - 1]
        if m not in order:
            order.append(m)
    monthly_rows = [{"month": m, "days": monthly[m]["days"], "etc_mm": monthly[m]["etc_mm"],
                     "net_m3_ha": monthly[m]["etc_mm"] * 10, "gross_m3_ha": monthly[m]["etc_mm"] * gross_factor * 10}
                    for m in order]

    net = sim["season_etc_mm"]
    out = {
        "soil": soil, "method": method, "application_efficiency": ea,
        "water_ecw_ds_m": ecw_ds_m, "leaching_requirement": lr,
        "salt_tolerance": SALT_TOLERANCE.get(crop["key"]),
        "expected_yield_pct_from_salinity": salinity_yield_pct(crop["key"], ecw_ds_m),
        "season_net_mm": net, "season_net_m3_ha": net * 10,
        "season_gross_mm": net * gross_factor, "season_gross_m3_ha": net * gross_factor * 10,
        "season_net_hi_m3_ha": sim["season_etc_hi_mm"] * 10,
        "season_gross_hi_m3_ha": sim["season_etc_hi_mm"] * gross_factor * 10,
        "stages": stages, "monthly": monthly_rows, "notes": notes,
    }
    if area_per_plant:
        out["spacing_m"] = spacing_m
        out["plants_per_ha"] = 10000 / area_per_plant
        out["season_l_per_plant"] = net * area_per_plant
        out["season_gross_l_per_plant"] = net * area_per_plant * gross_factor
    return out
