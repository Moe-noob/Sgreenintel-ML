"""
Builds the shareable outputs for all 11 cities:

  outputs/report.html            self-contained interactive report (no server,
                                 no internet needed; open it in a browser)
  outputs/summary_11_cities.csv  one row per city x crop condition

Run:  python feature2_v2/report.py [--soil loamy_sand] [--method drip] [--ecw 1.5]
"""

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import climate                       # noqa: E402
from advisor import advise, NEGLIGIBLE_STRESS_DD   # noqa: E402

OUT = HERE / "outputs"


def _compact(res):
    crops = []
    for c in res["crops"]:
        cal = "".join("g" if r["candidate"] and r["stress_dd"] <= NEGLIGIBLE_STRESS_DD else
                      "w" if r["candidate"] else "n" for r in c["by_sowing_day"])
        item = {"crop": c["crop"], "ar": c["arabic"], "cond": "no FAO-56 reference climate given" if c["condition"] == "Undefined / Undefined" else c["condition"], "row": c["workbook_row"],
                "status": c["status"], "basis": c["basis"], "cal": cal, "th": c["thresholds"],
                "maxDays": round(c["max_season_days"]),
                "sf": [f"{w['from']} – {w['to']}" for w in c["windows_stress_free"]],
                "ok": [f"{w['from']} – {w['to']}" for w in c["windows_heat_sufficient"]],
                "paper": {"best": c["paper_method"]["best_date"],
                          "win": [f"{a} – {b}" for a, b in c["paper_method"]["windows_hu"]]}}
        if "best" in c:
            b, ir = c["best"], c["irrigation"]
            item["best"] = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in b.items()
                            if k in ("sow_doy", "sow_date", "harvest_date", "total_days", "stage_lengths",
                                     "season_et0_mm", "season_etc_mm", "season_etc_hi_mm", "peak_etc_mm_day",
                                     "peak_date", "heat_days", "cold_days", "heat_dd", "cold_dd")}
            item["ir"] = {"net": round(ir["season_net_m3_ha"]), "gross": round(ir["season_gross_m3_ha"]),
                          "netHi": round(ir["season_net_hi_m3_ha"]), "ea": ir["application_efficiency"],
                          "lr": round(ir["leaching_requirement"], 3),
                          "yieldPct": ir["expected_yield_pct_from_salinity"], "notes": ir["notes"],
                          "stages": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in s.items()}
                                     for s in ir["stages"]],
                          "monthly": [{"m": m["month"], "days": m["days"], "gross": round(m["gross_m3_ha"]),
                                       "net": round(m["net_m3_ha"])} for m in ir["monthly"]]}
            item["daily"] = {"etc": [round(d["etc"], 2) for d in c["daily"]],
                             "et0": [round(d["et0"], 2) for d in c["daily"]],
                             "date": [d["date"] for d in c["daily"]],
                             "stage": [d["stage"][0] for d in c["daily"]]}
        crops.append(item)
    return {"location": res["location"], "station": res["station"], "dist": res["station_distance_km"],
            "warnings": res["warnings"], "settings": res["settings"], "crops": crops}


def write_csv(results, path):
    cols = ["city", "station", "crop", "arabic", "workbook_row", "condition", "status", "best_sowing", "harvest",
            "season_days", "stages_ini_dev_mid_late", "heat_days", "cold_nights", "stress_degC_days",
            "et0_mm", "etc_mm", "net_m3_ha", "net_dry_air_bound_m3_ha", "gross_m3_ha", "peak_etc_mm_day",
            "low_stress_windows", "finishes_in_time_windows", "paper_method_best"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for city, res in results.items():
            for c in res["crops"]:
                b, ir = c.get("best"), c.get("irrigation")
                w.writerow([city, res["station"]["name"], c["crop"], c["arabic"], c["workbook_row"], c["condition"],
                            c["status"],
                            b and b["sow_date"], b and b["harvest_date"], b and b["total_days"],
                            b and "/".join(map(str, b["stage_lengths"])), b and b["heat_days"], b and b["cold_days"],
                            b and round(b["stress_dd"], 1), b and round(b["season_et0_mm"]),
                            b and round(b["season_etc_mm"]), ir and round(ir["season_net_m3_ha"]),
                            ir and round(ir["season_net_hi_m3_ha"]), ir and round(ir["season_gross_m3_ha"]),
                            b and round(b["peak_etc_mm_day"], 2),
                            "; ".join(f"{x['from']}-{x['to']}" for x in c["windows_stress_free"]),
                            "; ".join(f"{x['from']}-{x['to']}" for x in c["windows_heat_sufficient"]),
                            c["paper_method"]["best_date"]])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--soil", default="loamy_sand")
    ap.add_argument("--method", default="drip")
    ap.add_argument("--ecw", type=float, default=None)
    a = ap.parse_args(argv)
    OUT.mkdir(exist_ok=True)
    results = {city: advise(city, a.soil, a.method, a.ecw) for city in climate.KNOWN_CITIES}
    write_csv(results, OUT / "summary_11_cities.csv")
    data = {city: _compact(r) for city, r in results.items()}
    template = (HERE / "report_template.html").read_text(encoding="utf-8")
    html = template.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    (OUT / "report.html").write_text(html, encoding="utf-8")
    print(f"wrote {OUT / 'report.html'} ({len(html) / 1e3:.0f} kB) and {OUT / 'summary_11_cities.csv'}")


if __name__ == "__main__":
    main()
