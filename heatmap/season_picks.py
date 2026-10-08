"""
Two planting seasons per crop: an AUTUMN pick and a SPRING pick, side by side.

Why
---
A single "best date" has to pick a winner between two references that disagree (research/selection_rules_vs_aquacrop.py,
33 city x crop combinations, NASA 2016-2025 climate with the elevation and humidity corrections):

  * AquaCrop (FAO crop model) ranks dates by water productivity (yield per m3). Our water-per-day rule agrees with it
    almost perfectly (31/33 combinations within 5 % of AquaCrop's best water productivity, against all viable dates), and almost always lands in autumn.
  * Saudi regional-directorate sowing calendars (Alsadon 2002, Table 5) very often list SPRING dates for the same crops
    (tomato in Tabuk Apr-May, in Qassim Jan-Mar). Stress-first rules agree with those calendars better but lose
    heavily to AquaCrop (tomato median regret 31 %), so no single rule satisfies both. Five calendar cases cannot separate
    the rules statistically, and the calendars also reflect frost, markets and tradition that AquaCrop does not model.

So the advisor reports both seasons, labelled, and says what the spring choice costs according to AquaCrop.

Definitions
-----------
  autumn = sowing on Jul 15 - Dec 31 (start_doy > 195); pick = least water per day, among shock-free dates when any exist
           (the same rule as the headline pick, restricted to this season).
  spring = sowing on Jan 1 - Jul 14 (start_doy <= 195); pick = least water per day among the dates within 5 degree-days of the
           least temperature stress (stress = degree-days of daily Tmax above the crop's crTmax plus Tmin below its crTmin
           over the whole season, on the smoothed climatology; Elnesr & Alazba 2016 tolerances).
The headline pick of each crop card (scan["best"]) is unchanged for the AquaCrop-checked crops (tomato, potato, corn) and for every
crop without a "headline_rule" in crop_database.py.

Headline override for lower-confidence warm-season crops
--------------------------------------------------------
Crops whose CROP_DB entry says "headline_rule": "fewest_exceedance_days" (cucumber, eggplant, squash, pumpkin, green bean) are not
covered by the AquaCrop validation that supports the least-water-per-day rule, and that rule keeps choosing winter sowings for
them (median 56-77 cold days for cucumber, eggplant and pumpkin). For these crops BOTH season picks and the card headline use one
measure, exceedance days (days over the whole season with Tmax or Tmin outside the crop's tolerance limits): the spring pick is the
spring date with the fewest exceedance days (ties: lower water per day), and the card headline is whichever of the autumn and spring
picks has fewer exceedance days (ties: lower water per day). This guarantees the headline is never worse, in exceedance days, than
the default rule's choice (an earlier degree-day spring pick was worse in 3 of 55 city x crop cases by 2-6 days). scan["best"],
scan["selection_basis"] and the headline label are replaced accordingly; the rule's original choice is kept in
scan["best_default_rule"]. No validation backs this override either: it follows the crop's own temperature tolerances and the
Saudi directorate calendars (spring picks inside the window in 4 of 5 cases, against about 3.2 expected by chance).

The AquaCrop cost table below
-----------------------------
SPRING_COST_PCT[crop][city] = how much LOWER AquaCrop's water productivity is for the spring pick than for the best date of the
whole year, rounded to a percent. Generated on 2026-10-01 with the same logic as research/selection_rules_vs_aquacrop.py:
AquaCrop 3.1.0, sandy loam, net irrigation, NASA POWER 2016-2025 normals with site-elevation and FAO-56 Rev.1 humidity corrections.
AquaCrop crop files exist only for tomato, corn and potato; bell pepper is NOT validated and shows no cost figure.
Regenerate it after ANY change to the climate, Kc or season-length logic. For locations that are not one of the 11 cities the
crop-wide median and range (CROP_SUMMARY) are shown instead.
"""

from crop_database import CROP_DB

SPLIT_DOY = 195            # start_doy <= 195 -> "spring" (Jan 1 - Jul 14); later -> "autumn" (Jul 15 - Dec 31)
STRESS_TIE_DD = 5.0        # degree-days: spring dates this close to the least stress count as equally safe

SPRING_COST_PCT = {
    "Tomato": {"riyadh": 48, "jeddah": 22, "dammam": 36, "najran": 32, "jazan": 13, "abha": 31, "tabuk": 53, "qassim": 52, "madinah": 32, "makkah": 24, "hail": 55},
    "Corn_(maize)": {"riyadh": 45, "jeddah": 18, "dammam": 34, "najran": 26, "jazan": 10, "abha": 30, "tabuk": 43, "qassim": 47, "madinah": 31, "makkah": 21, "hail": 44},
    "Potato": {"riyadh": 34, "jeddah": 15, "dammam": 24, "najran": 24, "jazan": 7, "abha": 25, "tabuk": 41, "qassim": 37, "madinah": 24, "makkah": 17, "hail": 44},
}

CROP_SUMMARY = {
    "Tomato": {"median": 32, "low": 13, "high": 55, "n": 11},
    "Corn_(maize)": {"median": 31, "low": 10, "high": 47, "n": 11},
    "Potato": {"median": 24, "low": 7, "high": 44, "n": 11},
}


def _stress_dd(run, clim, crop):
    tx_tol, tn_tol = CROP_DB[crop]["t_max_tolerable"], CROP_DB[crop]["t_min_tolerable"]
    total = 0.0
    for n in range(run["total_days"]):
        d = clim[(run["start_doy"] - 1 + n) % 365]
        total += max(0.0, d["temp_max_c"] - tx_tol) + max(0.0, tn_tol - d["temp_min_c"])
    return total


def compute_season_picks(crop_name, scan, clim, city_key=None):
    """Returns the season_picks dict for one crop scan (see add_season_picks), or None if the crop has no viable date."""
    viable = [r for r in scan["runs"] if r["viable"]]
    if not viable or CROP_DB[crop_name].get("t_max_tolerable") is None:
        return None
    mean = lambda r: r["seasonal_etc_mm"] / r["total_days"]
    autumn = [r for r in viable if r["start_doy"] > SPLIT_DOY]
    spring = [r for r in viable if r["start_doy"] <= SPLIT_DOY]

    a = None
    if autumn:
        pool = [r for r in autumn if r["shock_free"]] or autumn
        a = min(pool, key=mean)
    s = s_dd = None
    by_days = CROP_DB[crop_name].get("headline_rule") == "fewest_exceedance_days"
    if spring:
        dd = {r["start_doy"]: _stress_dd(r, clim, crop_name) for r in spring}
        if by_days:       # lower-confidence crops: same measure as their headline (see module docstring)
            s = min(spring, key=lambda r: (r["heat_shock_days"] + r["cold_shock_days"], mean(r)))
        else:             # AquaCrop-tied rule: least degree-day stress, near-ties broken by water
            least = min(dd.values())
            s = min([r for r in spring if dd[r["start_doy"]] <= least + STRESS_TIE_DD], key=mean)
        s_dd = dd[s["start_doy"]]

    best = scan.get("best")
    headline = None
    if best is not None:
        headline = "autumn" if a and best["start_doy"] == a["start_doy"] else ("spring" if s and best["start_doy"] == s["start_doy"] else None)

    cost = None
    if s is not None and crop_name in CROP_SUMMARY:
        per_city = SPRING_COST_PCT.get(crop_name, {}).get(city_key)
        summ = CROP_SUMMARY[crop_name]
        cost = {"pct": per_city if per_city is not None else summ["median"],
                "scope": "this city" if per_city is not None else "median of the 11 validated cities",
                "low": summ["low"], "high": summ["high"], "n": summ["n"]}
    return {
        "split_doy": SPLIT_DOY, "autumn_starts": "Jul 15 - Dec 31", "spring_starts": "Jan 1 - Jul 14",
        "autumn": {"start_doy": a["start_doy"], "rule": "least water per day among autumn dates (shock-free dates first)"} if a else None,
        "spring": {"start_doy": s["start_doy"], "stress_degree_days": round(s_dd, 1),
                   "rule": ("fewest days outside the crop's temperature limits among spring dates, ties broken by water per day" if by_days else
                    "least temperature stress among spring dates, ties broken by water per day")} if s else None,
        "headline": headline,
        "spring_cost": cost,
        "spring_cost_note": ("Regional planting calendars often use spring dates; they also reflect frost risk and market timing, "
                             "which AquaCrop does not model.") if cost else "Not checked against AquaCrop for this crop.",
    }


def add_season_picks(crop_name, scan, clim, city_key=None):
    picks = compute_season_picks(crop_name, scan, clim, city_key)
    scan["season_picks"] = picks
    crop = CROP_DB[crop_name]
    scan["confidence"] = crop.get("confidence")
    scan["confidence_note"] = crop.get("confidence_note")
    scan["headline_rule"] = crop.get("headline_rule")
    if picks and crop.get("headline_rule") == "fewest_exceedance_days" and picks["autumn"] and picks["spring"] and scan.get("best"):
        runs = {r["start_doy"]: r for r in scan["runs"]}
        a, s = runs[picks["autumn"]["start_doy"]], runs[picks["spring"]["start_doy"]]
        exceed = lambda r: r["heat_shock_days"] + r["cold_shock_days"]
        winner = min((a, s), key=lambda r: (exceed(r), r["seasonal_etc_mm"] / r["total_days"]))
        original = scan["best"]
        scan["best_default_rule"] = {"start_doy": original["start_doy"], "start_date": original["start_date"],
                                     "exceedance_days": original["heat_shock_days"] + original["cold_shock_days"]}
        scan["best"] = winner
        scan["selection_basis"] = ("fewest exceedance days (heat + cold) among the autumn and spring picks, ties broken by lower water "
                                   "per day. Lower-confidence crop: its heat units are a min/max range and AquaCrop cannot check it")
        picks["headline"] = "autumn" if winner is a else "spring"
    return picks


def season_picks_lines(scan):
    """Console lines for advisor.print_recommendations."""
    sp = scan.get("season_picks")
    if not sp:
        return []
    runs = {r["start_doy"]: r for r in scan["runs"]}
    out = ["   Two planting seasons (the headline date above is unchanged):"]
    for key, label in (("autumn", "Autumn (Jul 15 - Dec 31 starts)"), ("spring", "Spring (Jan 1 - Jul 14 starts)")):
        p = sp.get(key)
        if not p:
            out.append(f"     {label}: no viable start date")
            continue
        r = runs[p["start_doy"]]
        tag = "  <- headline" if sp.get("headline") == key else ""
        out.append(f"     {label}: {r['start_date']} -> {r['end_date']}, {r['total_days']} days, {r['seasonal_etc_mm']:.0f} mm "
                   f"({r['seasonal_etc_mm'] / r['total_days']:.1f} mm/day), exceedance days {r['heat_shock_days']} heat / "
                   f"{r['cold_shock_days']} cold{tag}")
    c = sp.get("spring_cost")
    if c:
        out.append(f"     AquaCrop: the spring date has about {c['pct']}% lower water productivity than the year's best date "
                   f"({c['scope']}; range {c['low']}-{c['high']}% across {c['n']} cities). Calendars often plant in spring; "
                   f"they also reflect frost and market timing.")
    else:
        out.append("     Spring option not checked against AquaCrop for this crop.")
    return out