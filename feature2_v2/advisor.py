"""
Feature 2 v2 -- location-based planting-date and water advisor for KSA.

For a location it answers, per crop:
  * When can I sow here?        (windows, from all 365 candidate days)
  * Which day is best?          (validated optimisation index; plus a lowest-risk alternative)
  * How long is the season here, stage by stage?
  * How much water per stage, per month and per season -- net and gross
    (after system efficiency and salt leaching), per hectare and per plant?
  * How often to irrigate?

Decision rule for each sowing day j
  1. Heat sufficiency: the crop must accumulate its heat-unit requirement
     (Elnesr & Alazba Eq. 7, HU_min over the FAO-56 season) within
     DUR_total x (1 + Htol/100) days, i.e. the paper's own heat tolerance
     applied to season length. Slower = too cold to finish in time.
  2. Temperature stress over the WHOLE season (not only the sowing day):
     degree-days of climatological Tmax above crTmax plus Tmin below crTmin.
  3. Best date = the Elnesr & Alazba (2016) optimisation-index day
     (exact spreadsheet method, verified engine), taken from the paper's
     "yellow band" (heat units AND sowing-day temperature OK) if it has one,
     else from its heat-units-only band -- in both cases only if the crop can
     finish in time from that day (rule 1); otherwise the lowest-risk date.
  4. Lowest-risk date = among dates passing 1, the least stress (degree-days,
     rounded), then the lowest seasonal ETc -- reported as an alternative.
  Why: against the sowing dates recommended by the regional Directorates
  of Agriculture (Alsadon 2002, Table 5; 16 crop x region cases;
  validation/alsadon2002.py) this rule put the best date inside the
  directorate window in 10/16 cases vs 9/16 for the lowest-risk rule alone
  (9/16 after season lengths moved to FAO-56 Rev.1; the paper's index alone
  scores 11/16). Using the heat-units-only index first scored 12/16 but sows
  garlic in Qassim in late July (43 degC), an agronomic error that the
  temperature condition prevents; with 16 cases these differences are
  within noise. The rule was chosen AFTER seeing the benchmark; no numeric
  parameter was fitted to it.
  Status: "recommended" if at least one date has negligible stress
  (<= NEGLIGIBLE_STRESS_DD over the season), "possible with temperature
  risk" if dates finish in time but all carry stress, "not suitable" if no
  date passes 1.
The paper's own spreadsheet result (heat units over DurTherm, sowing-day
temperature test, combined index) is computed with the verified engine and
reported alongside for comparison.

Usage
  python feature2_v2/advisor.py riyadh
  python feature2_v2/advisor.py 24.7 46.7 --crop Tomato --soil sandy_loam --ecw 2.0 --spacing 1.2 0.4
  python feature2_v2/advisor.py --all-cities --json outputs/
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import climate                       # noqa: E402
import elnesr_model as em            # noqa: E402
from crops import ksa_crops          # noqa: E402
from irrigation import plan          # noqa: E402
from season import simulate, doy_label   # noqa: E402

NEGLIGIBLE_STRESS_DD = 5.0   # degC-days over a whole season; below the precision of long-term means
HU_WEIGHT = 0.75   # spreadsheet default slider position (Model!D24); only affects the paper-index comparison


def _windows(days_ok):
    """Contiguous runs over a cyclic year; days_ok is a list of 365 bools (index 0 = 1 Jan)."""
    runs, start = [], None
    for i, ok in enumerate(days_ok + [False]):
        if ok and start is None:
            start = i + 1
        if not ok and start is not None:
            runs.append([start, i])
            start = None
    if len(runs) > 1 and runs[0][0] == 1 and runs[-1][1] == 365:
        runs[0] = [runs[-1][0], runs[0][1]]
        runs.pop()
    return [{"from": doy_label(a), "to": doy_label(b), "from_doy": a, "to_doy": b,
             "days": (b - a) % 365 + 1} for a, b in runs]


def analyse_crop(crop, station, soil="loamy_sand", method="drip", ecw=None, spacing=None):
    paper = em.run({k: station.fit(k) for k in ("Tx", "Tn", "Ta", "ET0")},
                   em.params_from_crop(crop, HU_WEIGHT))
    sims = [simulate(crop, station, d) for d in range(1, 366)]
    max_days = crop["dur_total"] * (1 + crop["heat_tol_pct"] / 100)
    rows = []
    for r, s in zip(paper["rows"], sims):
        ok = s["viable"] and s["total_days"] <= max_days
        rows.append({"doy": r["doy"], "paper_hu_ok": bool(r["flag_hu"]), "paper_sow_temp_ok": bool(r["flag_tmax"] and r["flag_tmin"]),
                     "viable": s["viable"], "candidate": ok,
                     "stress_days": (s["heat_days"] + s["cold_days"]) if s["viable"] else None,
                     "stress_dd": round(s["stress_dd"], 1) if s["viable"] else None,
                     "season_days": s.get("total_days"), "etc_mm": s.get("season_etc_mm")})
    cands = [(r, s) for r, s in zip(rows, sims) if r["candidate"]]
    stress_free = [r["candidate"] and r["stress_dd"] <= NEGLIGIBLE_STRESS_DD for r in rows]
    best = low_risk = None
    best_rule = None
    if cands:
        lr_row, _ = min(cands, key=lambda rs: (round(rs[1]["stress_dd"]), rs[1]["season_etc_mm"]))
        low_risk = simulate(crop, station, lr_row["doy"], detail=True)
        best, best_rule = low_risk, "lowest_risk"
        for rule, d in (("paper_index_hu_temp", paper["best_doy_hu_temp"]), ("paper_index_hu", paper["best_doy"])):
            d = int(round(d)) if d else None
            if d and rows[d - 1]["candidate"]:
                best, best_rule = simulate(crop, station, d, detail=True), rule
                break
    if best is None:
        status, basis = "not_suitable", (f"too cold: no sowing date lets the crop finish within "
                                         f"{max_days:.0f} days (FAO-56 {crop['dur_total']:.0f} d + {crop['heat_tol_pct']:.0f}% tolerance)")
    elif any(stress_free):
        status, basis = "recommended", "there are sowing dates with negligible temperature stress"
    else:
        status, basis = "possible_with_risk", ("every date that finishes in time has temperatures beyond the crop's "
                                               "tolerable limits (long-term means)")
    if best is not None:
        basis += ("; best date from the Elnesr & Alazba optimisation index" if best_rule.startswith("paper_index")
                  else "; best date = least temperature stress, then least water (the paper's index date "
                       "does not let the crop finish in time here)")
    result = {
        "crop": crop["key"], "arabic": crop["arabic"], "condition": f"{crop['region']} / {crop['plant_date']}",
        "workbook_row": crop["number"], "status": status, "basis": basis,
        "thresholds": {k: crop[k] for k in ("t_base", "t_opt", "t_max", "t_min", "heat_tol_pct", "dur_therm")},
        "max_season_days": max_days, "n_candidates": len(cands), "n_stress_free": sum(stress_free),
        "windows_stress_free": _windows(stress_free),
        "windows_heat_sufficient": _windows([r["candidate"] for r in rows]),
        "paper_method": {
            "note": "exact Elnesr & Alazba (2016) spreadsheet method on the same station data",
            "hu_min": paper["hu_min"], "hu_max": paper["hu_max"], "kc_eq": paper["kc_eq"], "dur_therm": paper["dur"],
            "best_date": doy_label(paper["best_doy"]) if paper["best_doy"] else None,
            "windows_hu": [[doy_label(a), doy_label(b)] for a, b in paper["hu_windows"]],
            "windows_hu_and_sowing_day_temp": [[doy_label(a), doy_label(b)] for a, b in paper["hu_temp_windows"]],
        },
        "by_sowing_day": rows,
    }
    if best:
        result["best"] = {k: v for k, v in best.items() if k != "daily"}
        result["irrigation"] = plan(crop, best, soil, method, ecw, spacing)
        result["best_rule"] = best_rule
        result["daily"] = [{k: round(v, 3) if isinstance(v, float) else v for k, v in d.items()} for d in best["daily"]]
        result["lowest_risk"] = {k: v for k, v in low_risk.items() if k not in ("daily", "stages")}
        lr_plan = plan(crop, low_risk, soil, method, ecw, spacing)
        result["lowest_risk"]["gross_m3_ha"] = lr_plan["season_gross_m3_ha"]
        result["lowest_risk"]["net_m3_ha"] = lr_plan["season_net_m3_ha"]
    return result


def advise(location, soil="loamy_sand", method="drip", ecw=None, spacing=None, crop_filter=None):
    loc = climate.resolve(location)
    st = loc["station"]
    crops = [c for c in ksa_crops() if not crop_filter or crop_filter.lower() in c["key"].lower()]
    results = [analyse_crop(c, st, soil, method, ecw, spacing) for c in crops]
    order = {"recommended": 0, "possible_with_risk": 1, "not_suitable": 2}
    results.sort(key=lambda r: (order[r["status"]], -r["n_stress_free"],
                                r.get("irrigation", {}).get("season_gross_m3_ha", 1e9)))
    return {
        "location": loc["label"], "lat": loc["lat"], "lon": loc["lon"],
        "station": st.summary(), "station_distance_km": round(loc["distance_km"], 1),
        "warnings": loc["warnings"],
        "settings": {"soil": soil, "irrigation_method": method, "water_ecw_ds_m": ecw, "spacing_m": spacing},
        "crops": results,
    }


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_report(res, show_stages=True):
    s = res["station"]
    print(f"\n=== {res['location']}  ->  station {s['name']} ({s['distance_km'] if 'distance_km' in s else res['station_distance_km']} km, "
          f"{s['elevation_m']} m)  ===")
    print(f"    Climate: FAOCLIM-2 long-term means (Elnesr & Alazba 2016 fits). Hottest Tmax {s['tmax_hottest_c']} C, "
          f"coldest Tmin {s['tmin_coldest_c']} C, ET0 {s['et0_annual_mm']} mm/yr (peak {s['et0_peak_mm_day']} mm/day)")
    st = res["settings"]
    print(f"    Settings: {st['irrigation_method']} irrigation, {st['soil']} soil, water ECw "
          f"{st['water_ecw_ds_m'] if st['water_ecw_ds_m'] else 'fresh'}")
    for w in res["warnings"]:
        print(f"    WARNING: {w}")
    for c in res["crops"]:
        tag = {"recommended": "RECOMMENDED", "possible_with_risk": "POSSIBLE, WITH TEMPERATURE RISK",
               "not_suitable": "NOT SUITABLE"}[c["status"]]
        print(f"\n{c['crop']} ({c['arabic']}) [{c['condition']}]  -> {tag}")
        if c["status"] == "not_suitable":
            print(f"   {c['basis']}")
            continue
        b, ir = c["best"], c["irrigation"]
        sf = "; ".join(f"{w['from']}-{w['to']}" for w in c["windows_stress_free"]) or "none"
        hu = "; ".join(f"{w['from']}-{w['to']}" for w in c["windows_heat_sufficient"]) or "none"
        print(f"   Low-stress sowing window(s):    {sf}")
        print(f"   Finishes-in-time window(s):     {hu}")
        lr = c["lowest_risk"]
        print(f"   Best sowing date: {b['sow_date']} -> harvest ~{b['harvest_date']} ({b['total_days']} days, "
              f"stages {'/'.join(map(str, b['stage_lengths']))}; {b['length_method']})")
        print(f"   Temperature stress: {b['heat_days']} hot day(s) (Tmax>{c['thresholds']['t_max']}, {b['heat_dd']:.0f} degC-days), "
              f"{b['cold_days']} cold night(s) (Tmin<{c['thresholds']['t_min']}, {b['cold_dd']:.0f} degC-days)")
        if lr["sow_doy"] != b["sow_doy"]:
            print(f"   Lowest-risk alternative: {lr['sow_date']} -> ~{lr['harvest_date']} ({lr['total_days']} days, "
                  f"stress {lr['stress_dd']:.0f} degC-days, gross {lr['gross_m3_ha']:.0f} m3/ha)")
        pm = c["paper_method"]
        print(f"   Paper method (Elnesr & Alazba spreadsheet): best {pm['best_date'] or 'none'}; HU windows "
              f"{'; '.join(a + '-' + b for a, b in pm['windows_hu']) or 'none'}")
        print(f"   Water: ETc {b['season_etc_mm']:.0f} mm = {ir['season_net_m3_ha']:.0f} m3/ha net "
              f"(dry-air bound {ir['season_net_hi_m3_ha']:.0f});  gross {ir['season_gross_m3_ha']:.0f} m3/ha "
              f"(Ea {ir['application_efficiency']:.0%}, LR {ir['leaching_requirement']:.0%}); peak {b['peak_etc_mm_day']:.1f} mm/day ~{b['peak_date']}")
        if ir.get("expected_yield_pct_from_salinity") is not None:
            y = ir["expected_yield_pct_from_salinity"]
            rng = f"{y['low']:.0f}%" if round(y["low"]) == round(y["high"]) else f"{y['low']:.0f}-{y['high']:.0f}%"
            print(f"   Salinity: expected relative yield {rng} at ECw {ir['water_ecw_ds_m']} dS/m (FAO-56 Rev.1 Table 8.8)")
        if show_stages:
            print(f"      {'stage':<12}{'days':>5} {'dates':<16}{'ETc/day':>8}{'ETc mm':>8}{'gross m3/ha':>12}{'every':>7}{'L/plant/d':>11}")
            for r in ir["stages"]:
                every = f"{r['max_interval_days']}d" if r.get("max_interval_days") else "-"
                lpp = f"{r['gross_l_per_plant_day']:.2f}" if "gross_l_per_plant_day" in r else "-"
                print(f"      {r['stage']:<12}{r['days']:>5} {r['start'] + '-' + r['end']:<16}{r['etc_mm_day']:>8.2f}"
                      f"{r['etc_mm']:>8.0f}{r['gross_m3_ha']:>12.0f}{every:>7}{lpp:>11}")
        for n in ir["notes"]:
            print(f"   note: {n}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("location", nargs="*", help="city name or LAT LON")
    ap.add_argument("--crop", help="filter by crop name substring")
    ap.add_argument("--soil", default="loamy_sand", choices=sorted(__import__("agronomy").SOILS))
    ap.add_argument("--method", default="drip", choices=["drip", "sprinkler", "surface"])
    ap.add_argument("--ecw", type=float, default=None, help="irrigation water salinity, dS/m")
    ap.add_argument("--spacing", type=float, nargs=2, metavar=("ROW_M", "PLANT_M"))
    ap.add_argument("--all-cities", action="store_true")
    ap.add_argument("--json", metavar="DIR", help="write <city>.json files to DIR")
    ap.add_argument("--brief", action="store_true", help="omit stage tables")
    a = ap.parse_args(argv)

    if a.all_cities:
        locations = list(climate.KNOWN_CITIES)
    elif len(a.location) == 2:
        locations = [(float(a.location[0]), float(a.location[1]))]
    elif len(a.location) == 1:
        locations = [a.location[0]]
    else:
        ap.error("give a city, LAT LON, or --all-cities")

    for loc in locations:
        res = advise(loc, a.soil, a.method, a.ecw, tuple(a.spacing) if a.spacing else None, a.crop)
        if a.json:
            out = Path(a.json)
            out.mkdir(parents=True, exist_ok=True)
            name = loc if isinstance(loc, str) else f"{loc[0]:.2f}_{loc[1]:.2f}"
            (out / f"{name}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float))
        print_report(res, show_stages=not a.brief)


if __name__ == "__main__":
    main()
