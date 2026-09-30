"""
Side-by-side check of v1 (heatmap/) and v2 (feature2_v2/).

Run this on a machine with internet access (or a warm heatmap/cache/): v1
needs NASA POWER, which the environment v2 was built in could not reach.

  python feature2_v2/validation/compare_with_v1.py

It writes feature2_v2/validation/compare_with_v1_results.md with:
  1. Climate / ET0: annual and monthly ET0 of v1 (NASA POWER, FAO-PM computed
     by v1) vs v2 (FAOCLIM-2 station ET0) for the 11 cities.
  2. Same crop, same city, same sowing date: season length and seasonal ETc
     from both versions (tomato, potato, bell pepper -- the crops both have).
  3. The Alsadon (2002) directorate benchmark on the 5 cases whose crops v1
     covers (Tabuk potato & tomato, Al-Ahsa tomato, Qassim tomato, Jazan pepper):
     window precision/recall and best-date hits for v1 and v2.

--selftest runs the whole pipeline on a SYNTHETIC v1 climate built from the
FAOCLIM-2 sinusoids (constant humidity/wind/radiation). Its numbers mean
nothing; it only proves the script runs end to end.
"""

import datetime as dt
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V2 = HERE.parent
ROOT = V2.parent
sys.path.insert(0, str(V2))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "heatmap"))       # v1 modules (no name clashes with v2)

import alsadon2002 as A                            # noqa: E402
import climate                                     # noqa: E402
import season as v2season                          # noqa: E402
from advisor import analyse_crop                   # noqa: E402
from crops import ksa_crops, load_crop_table, prepare   # noqa: E402

import nasa_power                                  # noqa: E402  (v1)
import season_simulator as v1sim                   # noqa: E402  (v1)

V1_NAME = {"Tomato": "Tomato", "Potato": "Potato", "Sweet peppers {bell}": "Pepper,_bell"}
MONTH_END = [31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]


def _label(doy):
    return (dt.date(2023, 1, 1) + dt.timedelta(days=int(doy) - 1)).strftime("%b %d")


def v1_climate(lat, lon):
    return nasa_power.fetch_daily_climatology_full(lat, lon)


def _synthetic_v1_climate(lat, lon):
    """--selftest only: v1-format climatology from the FAOCLIM-2 sinusoids."""
    st = climate.nearest_station(lat, lon)[0]
    clim = [{"doy": j, "temp_max_c": st.tx(j), "temp_min_c": st.tn(j), "temp_c": st.ta(j),
             "dewpoint_c": st.tn(j) - 8, "wind_speed_ms": 2.5, "solar_radiation_mj": 22.0,
             "precip_mm_day": 0.2} for j in range(1, 366)]
    return clim, float(st.elevation_m), {}


def v1_et0_series(clim, elev, lat):
    return [v1sim._et0_for(clim[j - 1], elev, lat) for j in range(1, 366)]


def monthly(series):
    out, a = [], 0
    for b in MONTH_END:
        out.append(sum(series[a:b]))
        a = b
    return out


def section_climate(lines):
    lines += ["## 1. Reference evapotranspiration (ET0), mm", "",
              "| City | v1 NASA POWER (annual) | v2 FAOCLIM-2 station (annual) | v1 − v2 | v2 station |",
              "|---|---|---|---|---|"]
    monthly_rows = []
    for city, (lat, lon) in climate.KNOWN_CITIES.items():
        clim, elev, _ = v1_climate(lat, lon)
        e1 = v1_et0_series(clim, elev, lat)
        st = climate.resolve(city)["station"]
        e2 = [st.et0(j) for j in range(1, 366)]
        lines.append(f"| {city} | {sum(e1):.0f} | {sum(e2):.0f} | {(sum(e1) - sum(e2)) / sum(e2):+.0%} | {st.name} |")
        monthly_rows.append((city, monthly(e1), monthly(e2)))
    lines += ["", "Monthly ET0 (v1 / v2, mm):", "",
              "| City | " + " | ".join(dt.date(2023, m, 1).strftime("%b") for m in range(1, 13)) + " |",
              "|---|" + "---|" * 12]
    for city, m1, m2 in monthly_rows:
        lines.append(f"| {city} | " + " | ".join(f"{a:.0f}/{b:.0f}" for a, b in zip(m1, m2)) + " |")
    lines.append("")


def section_same_date(lines):
    lines += ["## 2. Same crop, city and sowing date (v2's best date)", "",
              "| City | Crop | Sow | v1 days (stages) | v2 days (stages) | v1 ETc mm | v2 ETc mm |",
              "|---|---|---|---|---|---|---|"]
    crops = [c for c in ksa_crops() if c["key"] in V1_NAME and c["number"] in (34, 70, 33)]
    for city, (lat, lon) in climate.KNOWN_CITIES.items():
        clim, elev, raw = v1_climate(lat, lon)
        st = climate.resolve(city)["station"]
        for c in crops:
            res = analyse_crop(c, st)
            if "best" not in res:
                continue
            d = res["best"]["sow_doy"]
            r1 = v1sim.simulate_annual_season(V1_NAME[c["key"]], clim, elev, lat, d, raw)
            b = res["best"]
            if r1["viable"]:
                v1_days = f"{r1['total_days']} ({'/'.join(map(str, r1['stage_lengths']))})"
                v1_etc = f"{r1['seasonal_etc_mm']:.0f}"
            else:
                v1_days, v1_etc = "not viable", "-"
            lines.append(f"| {city} | {c['key']} | {b['sow_date']} | {v1_days} | "
                         f"{b['total_days']} ({'/'.join(map(str, b['stage_lengths']))}) | {v1_etc} | {b['season_etc_mm']:.0f} |")
    lines.append("")


def _pr(s):
    prec = "-" if s["precision"] is None else f"{s['precision']:.0%}"
    return f"{prec}/{s['recall']:.0%}"


def section_benchmark(lines):
    lines += ["## 3. Alsadon (2002) directorate benchmark, cases both versions cover", "",
              "| Region | Crop | Directorate | v1 window prec/recall | v2 window prec/recall | v1 best | v2 best |",
              "|---|---|---|---|---|---|---|"]
    table = load_crop_table()
    hits1 = hits2 = n = 0
    p1s, r1s, p2s, r2s = [], [], [], []
    for region, crop, rows, b_rng, _, b_ar, *_ in A.CASES:
        if crop not in V1_NAME:
            continue
        n += 1
        b = A.days(b_rng)
        lat, lon = A.REGIONS[region]
        clim, elev, raw = v1_climate(lat, lon)
        scan = v1sim.scan_planting_dates(V1_NAME[crop], clim, elev, lat, step_days=1, raw_years=raw)
        m1 = {r["start_doy"] for r in scan["runs"] if r["viable"] and r["shock_free"]} or \
             {r["start_doy"] for r in scan["runs"] if r["viable"]}
        best1 = scan["best"]["start_doy"] if scan["best"] else None
        st = climate.resolve((lat, lon))["station"]
        m2, best2 = set(), []
        for r in rows:
            res = analyse_crop(prepare(table[r]), st)
            m2 |= {x["doy"] for x in res["by_sowing_day"] if x["candidate"]}
            if "best" in res:
                best2.append(res["best"]["sow_doy"])
        s1, s2 = A.score(m1, b), A.score(m2, b)
        h1 = best1 in b if best1 else False
        h2 = any(d in b for d in best2)
        hits1 += h1
        hits2 += h2
        for s, P, R in ((s1, p1s, r1s), (s2, p2s, r2s)):
            if s["precision"] is not None:
                P.append(s["precision"])
            R.append(s["recall"])
        lines.append(f"| {region} | {crop} | {b_ar} | {_pr(s1)} | {_pr(s2)} | "
                     f"{_label(best1) if best1 else 'none'} {'IN' if h1 else 'out'} | "
                     f"{', '.join(_label(d) for d in best2) or 'none'} {'IN' if h2 else 'out'} |")
    mean = lambda x: f"{sum(x) / len(x):.0%}" if x else "-"
    lines += ["", f"Mean window precision / recall: v1 {mean(p1s)} / {mean(r1s)}, v2 {mean(p2s)} / {mean(r2s)}. "
              f"Best date inside the directorate window: v1 {hits1}/{n}, v2 {hits2}/{n}.",
              "", "v1 window = its shock-free viable dates (all viable dates if none are shock-free); "
              "v2 window = its 'finishes in time' dates. Both scanned daily.", ""]


def main():
    selftest = "--selftest" in sys.argv
    if selftest:
        global v1_climate
        v1_climate = _synthetic_v1_climate
    else:
        try:
            v1_climate(*climate.KNOWN_CITIES["riyadh"])
        except Exception as e:                                     # noqa: BLE001
            print(f"Could not load v1 climate (NASA POWER): {e}\n"
                  "Run on a machine with internet access, or after heatmap/prewarm_cache.py.")
            sys.exit(1)
    lines = ["# v1 vs v2 comparison", "",
             ("**SELF-TEST ON SYNTHETIC v1 CLIMATE -- numbers are meaningless.**" if selftest else
              f"Generated {dt.date.today()} by `feature2_v2/validation/compare_with_v1.py`."), ""]
    section_climate(lines)
    section_same_date(lines)
    section_benchmark(lines)
    out = HERE / ("compare_with_v1_selftest.md" if selftest else "compare_with_v1_results.md")
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
