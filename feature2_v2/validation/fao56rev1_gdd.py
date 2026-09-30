"""
Check of season lengths against FAO-56 Rev.1 (2025).

HISTORY: this script was first run against v2's original season-length
method (Elnesr & Alazba Eq. 7 heat units, capped at Topt). Result: only
8/210 city x crop cases inside the Rev.1 range, 188/210 LONGER than Rev.1
(e.g. cucumber, Makkah: 136 vs 54-90 days). season.py was therefore
switched to the Rev.1 GDD method for the 18 crops Rev.1 covers. Run with
--old to reproduce the original comparison.

v2 derives season length from Elnesr & Alazba's heat-unit requirement
((Topt - Tbase) x FAO-56 1998 duration, cutoff at Topt). FAO-56 Rev.1 now
publishes FIELD-OBSERVED growing-degree-day totals per crop (Table 6.11,
p. 209-210) or ranges derived from the 1998 durations (Table 6.12, p. 211),
computed with its own base/upper temperatures (Table 6.10, p. 204-205):

    GDD_day = min(max(Tavg - Tbase, 0), Tupper - Tbase)

For each city and crop, the season length that Rev.1 predicts at v2's best
sowing date is computed from the same station climate (short- and
long-season rows give a range), and v2's length is compared with it.
This is independent of v2's own method: different temperature thresholds
and different (observed) heat-unit totals.

Run:  python feature2_v2/validation/fao56rev1_gdd.py
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import climate                       # noqa: E402
import crops as crops_mod            # noqa: E402
from advisor import analyse_crop     # noqa: E402

# v2 crop key -> (Tbase, Tupper) [Table 6.10], (total GDD short/min, total GDD long/max) [Table 6.11 or 6.12], source row
REV1_GDD = {
    "Tomato": (7, 28, 1900, 2065, "6.11 Tomato, industry / market"),
    "Sweet peppers {bell}": (10, 35, 2415, 2415, "6.11 Bell pepper, common"),
    "Potato": (2, 30, 1600, 2260, "6.11 Potato, short / long season"),
    "Onions {dry}": (4.5, 35, 2290, 2290, "6.11 Onions, common"),
    "Lettuce": (4, 28, 985, 1290, "6.11 Lettuce, short / long"),
    "Carrots": (6, 30, 1575, 1575, "6.11 Carrots, common"),
    "Garlic": (4, 30, 1140, 1750, "6.11 Garlic, short / long"),
    "Broccoli": (4.5, 30, 755, 1280, "6.11 Broccoli, short / long"),
    "Sweet Melons": (10, 38, 1175, 1600, "6.11 Melon, short / long"),
    "Sweet corn": (10, 32, 985, 1485, "6.11 Maize, sweet, short / long"),
    "Beans, green": (10, 32, 450, 1170, "6.12 Bean, green, min / max"),
    "Cabbage": (4.5, 30, 1710, 1710, "6.12 Cabbage, common"),
    "Cauliflower": (4.5, 30, 1570, 1570, "6.12 Cauliflower, common"),
    "Spinach": (4, 25, 570, 610, "6.12 Spinach, min / max"),
    "Cucumber {Fresh Market}": (10, 32, 970, 1520, "6.12 Cucumber, min / max"),
    "EggPlant": (10, 35, 1180, 1430, "6.12 Eggplant, min / max"),
    "Squash": (10, 32, 630, 1150, "6.12 Squash, Zucchini, min / max"),
    "Lentil": (2, 35, 1850, 1930, "6.12 Lentil, min / max"),
}
TOLERANCE = 0.15      # "agrees" = within the Rev.1 range, or within 15 % of its nearer end


def days_to(station, sow_doy, tb, tu, target):
    cum = 0.0
    for n in range(730):
        ta = station.ta(sow_doy + n)
        cum += min(max(ta - tb, 0.0), tu - tb)
        if cum >= target:
            return n + 1
    return None


def main(write=True, old=False):
    rows = []
    if old:                          # reproduce the original comparison: drop the Rev.1 GDD data
        orig = crops_mod.prepare
        crops_mod.prepare = lambda r, k=None: {kk: vv for kk, vv in orig(r, k).items() if kk != "gdd_rev1"}
    for city in climate.KNOWN_CITIES:
        st = climate.resolve(city)["station"]
        for crop in crops_mod.ksa_crops():
            ref = REV1_GDD.get(crop["key"])
            if not ref:
                continue
            res = analyse_crop(crop, st)
            if "best" not in res:
                continue
            tb, tu, lo, hi, src = ref
            sow, v2_days = res["best"]["sow_doy"], res["best"]["total_days"]
            d_lo, d_hi = days_to(st, sow, tb, tu, lo), days_to(st, sow, tb, tu, hi)
            if d_lo is None or d_hi is None:
                continue
            a, b = min(d_lo, d_hi), max(d_lo, d_hi)
            inside = a <= v2_days <= b
            gap = 0 if inside else (a - v2_days if v2_days < a else v2_days - b)
            near = a if v2_days < a else b
            rows.append({"city": city, "crop": crop["key"], "row": crop["number"], "sow": res["best"]["sow_date"],
                         "v2_days": v2_days, "rev1_days": [a, b], "inside": inside,
                         "rel_gap": gap / near, "agrees": inside or gap / near <= TOLERANCE, "source": src})
    n = len(rows)
    inside = sum(r["inside"] for r in rows)
    agree = sum(r["agrees"] for r in rows)
    longer = sum(1 for r in rows if not r["agrees"] and r["v2_days"] > r["rev1_days"][1])
    print(f"{'city':9}{'crop':24}{'sow':>8}{'v2 days':>9}{'Rev.1 range':>14}  verdict")
    for r in rows:
        v = "inside" if r["inside"] else ("within 15%" if r["agrees"] else f"off {r['rel_gap']:.0%}")
        print(f"{r['city']:9}{r['crop'][:23]:24}{r['sow']:>8}{r['v2_days']:>9}{str(r['rev1_days'][0]) + '-' + str(r['rev1_days'][1]):>14}  {v}")
    print(f"\n{n} city x crop cases: {inside} inside the FAO-56 Rev.1 range ({inside / n:.0%}), "
          f"{agree} within it or 15 % of it ({agree / n:.0%}); of the rest, {longer} are longer than Rev.1, {n - agree - longer} shorter.")
    summary = {"cases": n, "inside": inside, "agree_15pct": agree, "longer": longer, "shorter": n - agree - longer}
    if old:
        crops_mod.prepare = orig
    if write:
        (HERE / ("fao56rev1_gdd_results_old_method.json" if old else "fao56rev1_gdd_results.json")).write_text(json.dumps({"summary": summary, "cases": rows}, indent=1))
    return rows, summary


if __name__ == "__main__":
    main(old="--old" in sys.argv)
