"""
Step 3 evidence: which planting-date SELECTION RULE should the advisor use?

Two independent references disagree, so we score every rule against both:

  1. AquaCrop (FAO's crop model), 33 city x crop combinations: regret = shortfall in AquaCrop water productivity
     (yield per m3 of ET) against AquaCrop's best date among ALL viable dates. Reuses research/cache/aquacrop_cache.json,
     so after the re-run of aquacrop_reference_check.py this takes about a minute (production scans only).
  2. Saudi regional-directorate sowing calendars (Alsadon 2002, Table 5), the 5 cases our crops cover. A hit means the
     rule's single recommended date falls inside the directorate window. Al-Ahsa has no city in our list; Dammam is used as
     a stand-in. This part needs no AquaCrop.

Rules (stress = degree-days of daily Tmax above the crop's crTmax plus Tmin below crTmin, over the whole season,
computed on the smoothed climatology, with Elnesr & Alazba tolerances):
  A  current          shock-free pool first, then least water per day
  B  stress first     least stress degree-days (rounded), then least water per day
  C  stress-aware     least water per day among dates within 5 degree-days of the least stress

Run from the project root (needs the AquaCrop cache; the Saudi part works without it):
    python research/selection_rules_vs_aquacrop.py
    python research/selection_rules_vs_aquacrop.py --cities=riyadh,tabuk --crops=tomato      (quick test)
    python research/selection_rules_vs_aquacrop.py --saudi-only
"""

import datetime as dt
import statistics as S
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aquacrop_reference_check as ac            # noqa: E402  (also puts heatmap/ on sys.path)

RULE_LABELS = {"A": "A  current (shock-free pool, least water/day)",
               "B": "B  stress first (degree-days), then least water/day",
               "C": "C  least water/day within 5 degree-days of least stress"}


def stress_dd(c, clim, crop):
    tx_tol, tn_tol = crop["t_max_tolerable"], crop["t_min_tolerable"]
    tot = 0.0
    for n in range(c["days"]):
        d = clim[(c["start_doy"] - 1 + n) % 365]
        tot += max(0.0, d["temp_max_c"] - tx_tol) + max(0.0, tn_tol - d["temp_min_c"])
    return tot


def choose(rule, cands):
    if rule == "A":
        return min([c for c in cands if c["shock_free"]] or cands, key=lambda c: c["per_day"])
    if rule == "B":
        return min(cands, key=lambda c: (round(c["dd"]), c["per_day"]))
    m = min(c["dd"] for c in cands)
    return min([c for c in cands if c["dd"] <= m + 5.0], key=lambda c: c["per_day"])


def label(doy):
    return (dt.date(2023, 1, 1) + dt.timedelta(days=int(doy) - 1)).strftime("%b %d")


# ------------------------------------------------------------------------------------------------ AquaCrop part
def run_aquacrop_part(cities, crops):
    cache = {}
    results = {}
    combos = [(c, k) for c in cities for k in crops]
    clims = {}
    for i, (city, crop_key) in enumerate(combos, 1):
        print(f"[{i}/{len(combos)}] {city} {crop_key} ...", flush=True)
        cands, _ok = ac.build_candidates(city, crop_key, cache)
        if city not in clims:
            lat, lon = ac.KNOWN_LOCATIONS[city]
            clims[city] = ac.fetch_daily_climatology_full(lat, lon)[0]
        crop = ac.CROP_DB[crop_key]
        for c in cands:
            c["dd"] = stress_dd(c, clims[city], crop)
        valid = [c for c in cands if "ac_wp" in c]
        if len(valid) < 3:
            continue
        best = max(valid, key=lambda c: c["ac_wp"])
        besty = max(valid, key=lambda c: c["ac_yield"])
        results[(city, crop_key)] = {r: (choose(r, valid), 1 - choose(r, valid)["ac_wp"] / best["ac_wp"],
                                         choose(r, valid)["ac_yield"] / besty["ac_yield"]) for r in "ABC"}

    n = len(results)
    print(f"\nAGREEMENT WITH AQUACROP over {n} city x crop combinations "
          f"(regret = shortfall in AquaCrop water productivity vs its best date among all viable dates)\n")
    print(f"{'rule':<58}{'median':>8}{'mean':>7}{'worst':>7}{'within 5%':>11}{'yield<75% of best':>19}")
    for r in "ABC":
        reg = [v[r][1] for v in results.values()]
        yr = [v[r][2] for v in results.values()]
        print(f"{RULE_LABELS[r]:<58}{S.median(reg)*100:>7.1f}%{S.mean(reg)*100:>6.1f}%{max(reg)*100:>6.1f}%"
              f"{sum(x <= 0.05 for x in reg):>8}/{n}{sum(y < 0.75 for y in yr):>14}/{n}")
    print("\nBy crop (median regret):")
    for crop_key in crops:
        row = [v for (cty, k), v in results.items() if k == crop_key]
        if row:
            print(f"  {crop_key:<14}" + "   ".join(f"{r}: {S.median([v[r][1] for v in row])*100:5.1f}%" for r in "ABC"))
    for r in "BC":
        worse = sorted(((v[r][1] - v["A"][1], k, v) for k, v in results.items()), reverse=True)[:6]
        print(f"\nWhere rule {r} loses most to AquaCrop compared with the current rule A (regret points):")
        for diff, (city, crop_key), v in worse:
            if diff <= 0.02:
                break
            print(f"  {city:<8} {crop_key:<13} A picks {v['A'][0]['start']} (regret {v['A'][1]*100:4.1f}%) -> {r} picks {v[r][0]['start']} "
                  f"(regret {v[r][1]*100:4.1f}%, yield {v[r][2]*100:3.0f}% of AquaCrop's best)")


# ------------------------------------------------------------------------------------------------ Saudi calendar part
def _doy(m, d):
    return dt.date(2023, m, min(d, [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])).timetuple().tm_yday


def window_days(ranges):
    out = set()
    for (m0, d0), (m1, d1) in ranges:
        a, b = _doy(m0, d0), _doy(m1, d1)
        out.update(range(a, b + 1) if a <= b else list(range(a, 366)) + list(range(1, b + 1)))
    return out


SAUDI_CASES = [  # (label, city used, crop, directorate window)   -- Alsadon (2002) Table 5
    ("Tabuk potato", "tabuk", "Potato", [((2, 1), (2, 28)), ((8, 1), (9, 30))]),
    ("Tabuk tomato", "tabuk", "Tomato", [((4, 1), (5, 31)), ((7, 1), (8, 31))]),
    ("Al-Ahsa tomato (Dammam stand-in)", "dammam", "Tomato", [((8, 1), (10, 15))]),
    ("Qassim tomato", "qassim", "Tomato", [((1, 1), (3, 31))]),
    ("Jazan bell pepper", "jazan", "Pepper,_bell", [((10, 1), (12, 31))]),
]


def run_saudi_part():
    print("\nSAUDI DIRECTORATE CALENDARS (Alsadon 2002, Table 5), the 5 cases our crops cover")
    print(f"{'case':<34}{'window = share of year':>24}   " + " | ".join(f"{r}: pick".ljust(14) for r in "ABC"))
    hits = {r: 0 for r in "ABC"}
    chance = 0.0
    for name, city, crop_key, rng in SAUDI_CASES:
        lat, lon = ac.KNOWN_LOCATIONS[city]
        clim, elev, raw = ac.fetch_daily_climatology_full(lat, lon)
        crop = ac.CROP_DB[crop_key]
        scan = ac.scan_planting_dates(crop_key, clim, elev, lat, step_days=10)
        cands = []
        for r in scan["runs"]:
            if r["viable"]:
                cands.append({"start_doy": r["start_doy"], "days": r["total_days"], "per_day": r["seasonal_etc_mm"] / r["total_days"],
                              "shock_free": r["shock_free"]})
        for c in cands:
            c["dd"] = stress_dd(c, clim, crop)
        win = window_days(rng)
        chance += sum(c["start_doy"] in win for c in cands) / len(cands)
        cells = []
        for r in "ABC":
            p = choose(r, cands)
            ok = p["start_doy"] in win
            hits[r] += ok
            cells.append(f"{label(p['start_doy'])} {'IN ' if ok else 'out'}".ljust(14))
        print(f"{name:<34}{len(win) / 365:>23.0%}   " + " | ".join(cells))
    print(f"\nBest date inside the directorate window (of {len(SAUDI_CASES)}):  A {hits['A']}   B {hits['B']}   C {hits['C']}"
          f"      expected by chance: {chance:.1f}")


def main():
    args = sys.argv[1:]
    opt = {a.split("=")[0]: a.split("=", 1)[1] for a in args if "=" in a}
    cities = opt.get("--cities", ",".join(ac.KNOWN_LOCATIONS)).split(",")
    crops = [ac.ALIASES.get(x.strip().lower(), x.strip()) for x in opt.get("--crops", "corn,tomato,potato").split(",")]
    if "--saudi-only" not in args:
        run_aquacrop_part(cities, crops)
    run_saudi_part()


if __name__ == "__main__":
    main()
