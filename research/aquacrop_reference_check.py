"""
Independent reference check for the planting-date selection rule.

QUESTION: when two candidate seasons are both free of exceedance days but differ
in length (e.g. 137 days vs 71 days), which is better, and which selection rule
picks it?

METHOD: FAO's AquaCrop model (Steduto et al. 2009, Agron. J. 101:426-437) is
used as an independent judge. It computes biomass as a crop constant times
cumulative transpiration normalised by ET0, then multiplies by a harvest index,
and it includes cold/heat stress on canopy and pollination. For every candidate
start date the SAME daily climate and the SAME ET0 (from our engine) drive both
models. AquaCrop returns yield and ET; from them: water productivity
WP = yield per m3 of ET. Our engine returns per-day water, total water and a
"water productivity index" (sum of Kc / sum of ETc, i.e. green-canopy days per
mm; the relative measure that follows from AquaCrop's normalisation).

Rules compared, each picking from the production's eligible pool (shock-free
dates if any exist, otherwise all viable dates):
  per-day (current)         lowest ETc per day
  total water               lowest whole-season ETc
  water productivity index  highest (sum Kc) / (sum ETc)
Score = REGRET: how far the rule's pick falls below the best date AquaCrop finds
in the same pool (0% = same water productivity as AquaCrop's best).

CAVEATS (state them): AquaCrop's built-in crop files (MaizeGDD, TomatoGDD,
PotatoGDD) are generic, not calibrated to Saudi cultivars, and use their own
thresholds, so their season lengths differ from ours; sandy-loam soil, full
irrigation (no water stress); smoothed daily-normal climate, so real-year
variability and extreme heat days are under-represented. This is a reference
for RANKING dates, not ground truth. AquaCrop has no pepper file, so pepper
cannot be checked. Research only: nothing in production changes.

Setup (research only, keep out of requirements.txt):
    pip install aquacrop

Usage:
    python research/aquacrop_reference_check.py                    # Najran corn, all dates (~20 s)
    python research/aquacrop_reference_check.py riyadh tomato      # another city/crop
    python research/aquacrop_reference_check.py --summary --quick  # 4 cities x 3 crops (~4 min)
    python research/aquacrop_reference_check.py --summary          # 11 cities x 3 crops (~10 min first time, then cached)
    python research/aquacrop_reference_check.py --guards           # only the stage-aware guard experiment (uses the cache)
    python research/aquacrop_reference_check.py --summary --only=potato --potato=PotatoGDD       # potato vs AquaCrop's shorter default potato
    python research/aquacrop_reference_check.py --quantity         # our seasonal ETc vs AquaCrop's ET (absolute mm), uses the cache
    crops: corn, tomato, potato
"""

import datetime as dt
import hashlib
import importlib.metadata
import json
import sys
import warnings
from pathlib import Path
from statistics import mean, median

import pandas as pd

# AquaCrop's PotatoLocalGDD file has a zero water-content parameter, so AquaCrop divides by zero when it
# converts DRY yield to FRESH yield and prints a warning on every run. We only use dry yield, so the
# warning is harmless; silence it so it cannot bury the results.
warnings.filterwarnings("ignore", category=RuntimeWarning, module=r"aquacrop\..*")

from aquacrop import AquaCropModel, Crop, InitialWaterContent, IrrigationManagement, Soil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

from crop_coefficients import kc_on_day  # noqa: E402
from crop_database import CROP_DB  # noqa: E402
from nasa_power import fetch_daily_climatology_full  # noqa: E402
from season_simulator import _et0_for, scan_planting_dates  # noqa: E402

KNOWN_LOCATIONS = {
    "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10),
    "najran": (17.49, 44.13), "jazan": (16.89, 42.55), "abha": (18.22, 42.51),
    "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98), "madinah": (24.47, 39.61),
    "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
}
QUICK_CITIES = ("riyadh", "najran", "jeddah", "tabuk")
# Potato: our engine needs 2,260 heat units; AquaCrop's PotatoGDD needs 1,276 and PotatoLocalGDD 1,613. The longer
# file is the closer match and agreed far better (median regret 2.1% vs 6.3%), so it is the default.
AC_CROPS = {"Corn_(maize)": "MaizeGDD", "Tomato": "TomatoGDD", "Potato": "PotatoLocalGDD"}
ALIASES = {"corn": "Corn_(maize)", "tomato": "Tomato", "potato": "Potato"}

RULES = (
    ("per-day (current)", "per-day", lambda c: c["per_day"]),
    ("total water", "total", lambda c: c["etc"]),
    ("water productivity index", "WPI", lambda c: -c["wpi"]),
)

FAILED_AQUACROP_RUNS = 0

# AquaCrop runs are the slow part (about 0.5 s each), so results are cached on disk. The cache key
# includes the AquaCrop version, the run settings, the crop file and a fingerprint of the exact
# weather, so any change to those simply misses the cache instead of returning stale numbers.
CACHE_PATH = Path(__file__).resolve().parent / "cache" / "aquacrop_cache.json"
AQUACROP_VERSION = importlib.metadata.version("aquacrop")
SETTINGS_TAG = "SandyLoam|net-irrigation-100|FC|2001-2002"
_CACHE = None


def _cache():
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            _CACHE = {}
    return _CACHE


def save_cache():
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(_cache()), encoding="utf-8")


def weather_fingerprint(wdf):
    return hashlib.md5(pd.util.hash_pandas_object(wdf, index=False).values.tobytes()).hexdigest()[:12]


def weather_frame(clim, elevation_m, latitude_deg):
    """Two calendar years (365 days each) of the daily normal, with our engine's own ET0."""
    rows = []
    for year in (2001, 2002):
        for i, d in enumerate(clim):
            rows.append({
                "MinTemp": d["temp_min_c"], "MaxTemp": d["temp_max_c"],
                "Precipitation": d["precip_mm_day"],
                "ReferenceET": _et0_for(d, elevation_m, latitude_deg),
                "Date": pd.Timestamp(year=year, month=1, day=1) + pd.Timedelta(days=i),
            })
    return pd.DataFrame(rows)


def run_aquacrop(wdf, ac_crop, start_doy, fingerprint):
    """Yield (dry t/ha) and growing-season ET (mm) for one planting date, or None. Cached on disk."""
    global FAILED_AQUACROP_RUNS
    key = f"{AQUACROP_VERSION}|{SETTINGS_TAG}|{ac_crop}|{fingerprint}|{start_doy}"
    cache = _cache()
    if key in cache:
        if cache[key] is None:
            FAILED_AQUACROP_RUNS += 1
        return cache[key]

    plant = dt.date(2001, 1, 1) + dt.timedelta(days=start_doy - 1)
    result = None
    try:
        model = AquaCropModel(
            "2001/01/01", "2002/12/31", wdf, Soil("SandyLoam"),
            Crop(ac_crop, planting_date=f"{plant.month:02d}/{plant.day:02d}"),
            initial_water_content=InitialWaterContent(value=["FC"]),
            irrigation_management=IrrigationManagement(irrigation_method=4, NetIrrSMT=100),
        )
        model.run_model(till_termination=True)
        res = model.get_simulation_results()
        if len(res) > 0:
            flux = model.get_water_flux()
            season = flux[(flux["season_counter"] == 0) & (flux["dap"] > 0)]
            result = {"ac_yield": float(res.iloc[0]["Dry yield (tonne/ha)"]),
                      "ac_et": float((season["Es"] + season["Tr"]).sum()),
                      "ac_days": int(len(season))}
    except Exception:
        result = None
    if result is None:
        FAILED_AQUACROP_RUNS += 1
    cache[key] = result
    return result


def kc_sum_and_etc(crop, run, clim, elevation_m, latitude_deg):
    """Recompute sum(Kc) and sum(ETc) day by day, exactly as the production loop does."""
    sum_kc = etc = 0.0
    for n in range(run["total_days"]):
        kc = kc_on_day(n, run["stage_lengths"], crop["kc_ini"],
                       run["kc_mid_adjusted"], run["kc_end_adjusted"])
        d = clim[(run["start_doy"] + n - 1) % 365]
        sum_kc += kc
        etc += kc * _et0_for(d, elevation_m, latitude_deg)
    return sum_kc, etc


def build_candidates(city, crop_key, weather_cache):
    lat, lon = KNOWN_LOCATIONS[city]
    clim, elevation_m, _raw = fetch_daily_climatology_full(lat, lon)
    crop = CROP_DB[crop_key]
    scan = scan_planting_dates(crop_key, clim, elevation_m, lat, step_days=10)
    if city not in weather_cache:
        frame = weather_frame(clim, elevation_m, lat)
        weather_cache[city] = (frame, weather_fingerprint(frame))
    wdf, fingerprint = weather_cache[city]
    txc, tnc = crop.get("t_max_tolerable"), crop.get("t_min_tolerable")

    cands, replica_ok = [], 0
    for r in scan["runs"]:
        if not r["viable"]:
            continue
        sum_kc, etc = kc_sum_and_etc(crop, r, clim, elevation_m, lat)
        replica_ok += abs(etc - r["seasonal_etc_mm"]) < 0.01
        # Exceedance days inside the mid-season stage only (the yield-sensitive stage)
        l_ini, l_dev, l_mid, _l_late = r["stage_lengths"]
        mid_heat = mid_cold = 0
        for n in range(l_ini + l_dev, l_ini + l_dev + l_mid):
            d = clim[(r["start_doy"] + n - 1) % 365]
            mid_heat += bool(txc is not None and d["temp_max_c"] > txc)
            mid_cold += bool(tnc is not None and d["temp_min_c"] < tnc)
        c = {"start_doy": r["start_doy"], "start": r["start_date"], "end": r["end_date"],
             "days": r["total_days"], "etc": r["seasonal_etc_mm"],
             "per_day": r["seasonal_etc_mm"] / r["total_days"],
             "sum_kc": sum_kc, "wpi": sum_kc / r["seasonal_etc_mm"],
             "heat": r["heat_shock_days"], "cold": r["cold_shock_days"],
             "mid_heat": mid_heat, "mid_cold": mid_cold,
             "mid_days": l_mid, "mid_exc": mid_heat + mid_cold,
             "shock_free": r["shock_free"]}
        ac = run_aquacrop(wdf, AC_CROPS[crop_key], r["start_doy"], fingerprint)
        if ac and ac["ac_yield"] > 0 and ac["ac_et"] > 0:
            c.update(ac)
            c["ac_wp"] = ac["ac_yield"] * 100 / ac["ac_et"]   # kg per m3 of ET (t/ha x1000 / (mm x10))
        cands.append(c)
    save_cache()
    return cands, replica_ok


def circ_days(a, b):
    d = abs(a - b)
    return min(d, 365 - d)


def contiguous_window(cands, pick, tol):
    """Dates adjacent (<= 10 days apart, wrapping the year) to the pick whose per-day water is
    within tol of the minimum; stops at the first date that breaks either condition."""
    cs = sorted(cands, key=lambda c: c["start_doy"])
    limit = min(c["per_day"] for c in cs) * (1 + tol)
    i = next(k for k, c in enumerate(cs) if c is pick)
    window = {i}
    for step in (1, -1):
        j = i
        for _ in range(len(cs)):
            k = (j + step) % len(cs)
            if k in window or circ_days(cs[j]["start_doy"], cs[k]["start_doy"]) > 10 or cs[k]["per_day"] > limit:
                break
            window.add(k)
            j = k
    return [cs[k] for k in sorted(window)]


def rank_corr(xs, ys):
    return pd.Series(xs).rank().corr(pd.Series(ys).rank())


def analyse(cands):
    pool = [c for c in cands if c["shock_free"]] or list(cands)
    valid = [c for c in pool if "ac_wp" in c]
    if len(valid) < 3:
        return None
    best_wp = max(valid, key=lambda c: c["ac_wp"])
    best_yield = max(valid, key=lambda c: c["ac_yield"])
    out = {"pool": len(pool), "valid": len(valid), "valid_cands": valid, "best_wp": best_wp,
           "best_yield": best_yield, "rules": {}}
    wps = [c["ac_wp"] for c in valid]
    for name, _short, key in RULES:
        pick = min(valid, key=key)
        out["rules"][name] = {
            "pick": pick,
            "wp_regret": 1 - pick["ac_wp"] / best_wp["ac_wp"],
            "y_regret": 1 - pick["ac_yield"] / best_yield["ac_yield"],
            "spearman": rank_corr([-key(c) for c in valid], wps),
        }
    return out


def print_detail(city, crop_key, cands, result):
    print(f"\n{crop_key} at {city}: {len(cands)} viable candidate dates, "
          f"eligible pool {result['pool']} ({'shock-free dates' if any(c['shock_free'] for c in cands) else 'no shock-free date, all viable'}), "
          f"{result['valid']} with an AquaCrop result")
    print(f"\n{'start':<8}{'days':>5}{'ETc mm':>8}{'mm/d':>6}{'SumKc':>7}{'WPI':>7}{'H/C':>9}{'midH/C':>9}"
          f"{'pool':>6}{'AC days':>9}{'AC yield':>9}{'AC ET':>7}{'AC WP':>7}  picked by")
    for c in cands:
        marks = [short for name, short, _k in RULES if result["rules"][name]["pick"] is c]
        if c is result["best_wp"]:
            marks.append("AC-best-WP")
        if c is result["best_yield"]:
            marks.append("AC-best-yield")
        in_pool = "yes" if (c["shock_free"] or not any(x["shock_free"] for x in cands)) else "no"
        ac = (f"{c['ac_days']:>9}{c['ac_yield']:>9.1f}{c['ac_et']:>7.0f}{c['ac_wp']:>7.2f}"
              if "ac_wp" in c else f"{'-':>9}{'-':>9}{'-':>7}{'-':>7}")
        print(f"{c['start']:<8}{c['days']:>5}{c['etc']:>8.0f}{c['per_day']:>6.2f}{c['sum_kc']:>7.1f}{c['wpi']:>7.3f}"
              f"{c['heat']:>5}/{c['cold']:<3}{c['mid_heat']:>5}/{c['mid_cold']:<3}{in_pool:>6}{ac}  {', '.join(marks)}")

    print("\nWhat each rule picks, and what AquaCrop says about it (regret vs AquaCrop's best in the pool):")
    print(f"{'rule':<26}{'start':<8}{'days':>5}{'ETc mm':>8}{'AC yield t/ha':>15}{'AC WP kg/m3':>13}{'WP regret':>11}{'yield regret':>14}{'Spearman':>10}")
    for name, _short, _k in RULES:
        r = result["rules"][name]
        p = r["pick"]
        print(f"{name:<26}{p['start']:<8}{p['days']:>5}{p['etc']:>8.0f}{p['ac_yield']:>15.1f}{p['ac_wp']:>13.2f}"
              f"{r['wp_regret']:>10.1%}{r['y_regret']:>14.1%}{r['spearman']:>10.2f}")
    b = result["best_wp"]
    print(f"{'AquaCrop best WP':<26}{b['start']:<8}{b['days']:>5}{b['etc']:>8.0f}{b['ac_yield']:>15.1f}{b['ac_wp']:>13.2f}")
    y = result["best_yield"]
    print(f"{'AquaCrop best yield':<26}{y['start']:<8}{y['days']:>5}{y['etc']:>8.0f}{y['ac_yield']:>15.1f}{y['ac_wp']:>13.2f}")


# ----------------------------------------------------------------------------------------------
# Stage-aware guard experiment. Every rule keeps the validated per-day key and differs only in the
# pool of dates it may choose from. Regret is measured against AquaCrop's best date among ALL
# viable dates, so the effect of the pool itself (not just the key) is included.
# ----------------------------------------------------------------------------------------------
def least_pool(v):
    m = min(c["mid_exc"] / c["mid_days"] for c in v)
    return [c for c in v if c["mid_exc"] / c["mid_days"] <= m + 1e-9]


def frac_pool(v, f):
    ok = [c for c in v if c["mid_exc"] / c["mid_days"] <= f]
    return ok or least_pool(v)


GUARD_RULES = (
    ("current: whole-season shock-free pool", "current", lambda v: [c for c in v if c["shock_free"]] or v),
    ("no exceedance filter at all", "none", lambda v: v),
    ("mid-season exceedance-free pool", "mid0", lambda v: [c for c in v if c["mid_exc"] == 0] or v),
    ("mid-season exceedance <= 10% of stage", "mid10", lambda v: frac_pool(v, 0.10)),
    ("mid-season exceedance <= 25% of stage", "mid25", lambda v: frac_pool(v, 0.25)),
    ("mid-season exceedance <= 50% of stage", "mid50", lambda v: frac_pool(v, 0.50)),
    ("least mid-season exceedance first", "least", least_pool),
)


def evaluate_guards(cands):
    valid = [c for c in cands if "ac_wp" in c]
    if len(valid) < 3:
        return None
    best = max(valid, key=lambda c: c["ac_wp"])
    best_yield = max(valid, key=lambda c: c["ac_yield"])
    out = {"best": best, "rules": {}}
    for _name, short, pool_fn in GUARD_RULES:
        pick = min(pool_fn(valid), key=lambda c: c["per_day"])
        out["rules"][short] = {"pick": pick, "wp_regret": 1 - pick["ac_wp"] / best["ac_wp"],
                               "y_ratio": pick["ac_yield"] / best_yield["ac_yield"]}
    return out


def print_guard_report(all_cands):
    res = {k: evaluate_guards(v) for k, v in all_cands.items()}
    res = {k: r for k, r in res.items() if r}
    n = len(res)
    if n == 0:
        print("No combinations to evaluate.")
        return
    cur = [r["rules"]["current"]["pick"] for r in res.values()]
    print(f"\n{'=' * 118}\nSTAGE-AWARE GUARD EXPERIMENT over {n} city x crop combinations "
          f"(regret vs AquaCrop's best date among ALL viable dates)\n{'=' * 118}")
    print(f"Current picks with ANY mid-season exceedance day: {sum(p['mid_exc'] > 0 for p in cur)}/{n}; "
          f"with more than 25% of the mid-season stage in exceedance: "
          f"{sum(p['mid_exc'] / p['mid_days'] > 0.25 for p in cur)}/{n}")

    print(f"\n{'rule':<40}{'median':>8}{'mean':>7}{'worst':>7}{'within 5%':>11}{'yield <75% of best':>20}{'picks changed':>15}")
    print("-" * 108)
    for name, short, _f in GUARD_RULES:
        regs = [r["rules"][short]["wp_regret"] for r in res.values()]
        lost = sum(1 for r in res.values() if r["rules"][short]["y_ratio"] < 0.75)
        changed = sum(1 for r in res.values()
                      if r["rules"][short]["pick"]["start_doy"] != r["rules"]["current"]["pick"]["start_doy"])
        print(f"{name:<40}{median(regs):>8.1%}{mean(regs):>7.1%}{max(regs):>7.1%}"
              f"{sum(1 for x in regs if x <= 0.05):>8}/{n:<2}{lost:>17}/{n:<2}{changed:>12}/{n:<2}")

    print(f"\nBy crop (median regret):")
    print(f"{'crop':<16}" + "".join(f"{short:>9}" for _n, short, _f in GUARD_RULES))
    for crop_key in AC_CROPS:
        row = [r for (c, k), r in res.items() if k == crop_key]
        if row:
            print(f"{crop_key:<16}" + "".join(f"{median([r['rules'][s]['wp_regret'] for r in row]):>9.1%}"
                                              for _n, s, _f in GUARD_RULES))

    for name, short, _f in GUARD_RULES[1:]:
        diffs = []
        for (city, crop_key), r in res.items():
            a, b = r["rules"]["current"], r["rules"][short]
            if abs(b["wp_regret"] - a["wp_regret"]) >= 0.03 and a["pick"]["start_doy"] != b["pick"]["start_doy"]:
                diffs.append((b["wp_regret"] - a["wp_regret"], city, crop_key, a, b))
        print(f"\nWhere '{short}' changes the answer by 3+ points of regret ({len(diffs)} combinations; "
              f"negative = better than current):")
        for d, city, crop_key, a, b in sorted(diffs, key=lambda x: x[0])[:6]:
            print(f"  {city:<9}{crop_key:<14}current {a['pick']['start']} (regret {a['wp_regret']:.1%}, "
                  f"mid exc {a['pick']['mid_exc']}/{a['pick']['mid_days']}) -> {short} {b['pick']['start']} "
                  f"(regret {b['wp_regret']:.1%}, mid exc {b['pick']['mid_exc']}/{b['pick']['mid_days']})  {d:+.1%}")


def run_guards(cities, cache, crops=None):
    crops = crops or list(AC_CROPS)
    print("AquaCrop crop files: " + ", ".join(f"{k}={AC_CROPS[k]}" for k in crops))
    combos = [(c, k) for c in cities for k in crops]
    all_cands = {}
    for i, (city, crop_key) in enumerate(combos, 1):
        print(f"[{i}/{len(combos)}] {city} {crop_key} ...", flush=True)
        all_cands[(city, crop_key)], _ok = build_candidates(city, crop_key, cache)
    print_guard_report(all_cands)


# ----------------------------------------------------------------------------------------------
# Water-quantity check: the ranking is validated elsewhere; this asks whether the ABSOLUTE numbers the
# app shows (mm, m3/ha) agree with an independent model. Ours = FAO-56 single-Kc crop evapotranspiration
# (sum of Kc x ET0). AquaCrop's = simulated soil evaporation + transpiration, which responds to canopy
# development and to cold/heat stress, so the two are expected to differ most in cold seasons.
# ----------------------------------------------------------------------------------------------
def print_quantity_report(all_cands):
    rows = []
    for (city, crop_key), cands in all_cands.items():
        valid = [c for c in cands if "ac_wp" in c]
        if len(valid) < 3:
            continue
        pool = [c for c in valid if c["shock_free"]] or valid
        pick = min(pool, key=lambda c: c["per_day"])
        rows.append({"city": city, "crop": crop_key, "pick": pick,
                     "ratio": pick["etc"] / pick["ac_et"], "days_ratio": pick["days"] / pick["ac_days"],
                     "all_ratio": median([c["etc"] / c["ac_et"] for c in valid]),
                     "corr": rank_corr([c["etc"] for c in valid], [c["ac_et"] for c in valid])})
    if not rows:
        print("No combinations to evaluate.")
        return
    print(f"\n{'=' * 112}\nWATER QUANTITY CHECK: our seasonal ETc vs AquaCrop's ET (evaporation + transpiration), "
          f"{len(rows)} combinations\nratio = ours / AquaCrop; 1.00 = identical, 1.20 = ours is 20% higher\n{'=' * 112}")
    print(f"\n{'crop':<16}{'n':>3}{'median ratio at pick':>22}{'range':>16}{'within +-15%':>14}"
          f"{'median ratio, all dates':>25}{'season-length ratio':>21}{'rank corr. across dates':>25}")
    print("-" * 112)
    groups = [(k, [r for r in rows if r["crop"] == k]) for k in AC_CROPS] + [("ALL", rows)]
    for name, g in groups:
        if not g:
            continue
        ratios = [r["ratio"] for r in g]
        print(f"{name:<16}{len(g):>3}{median(ratios):>22.2f}{f'{min(ratios):.2f}-{max(ratios):.2f}':>16}"
              f"{sum(1 for x in ratios if abs(x - 1) <= 0.15):>11}/{len(g):<2}"
              f"{median([r['all_ratio'] for r in g]):>25.2f}{median([r['days_ratio'] for r in g]):>21.2f}"
              f"{median([r['corr'] for r in g if r['corr'] == r['corr']]):>25.2f}")
    print("\nCombinations furthest from 1.00 at the pick:")
    for r in sorted(rows, key=lambda x: -abs(x["ratio"] - 1))[:8]:
        p = r["pick"]
        print(f"  {r['city']:<9}{r['crop']:<14}{p['start']}: ours {p['etc']:.0f} mm over {p['days']} d, AquaCrop {p['ac_et']:.0f} mm over "
              f"{p['ac_days']} d  (ratio {r['ratio']:.2f})")
    hi = [r for r in rows if r["ratio"] > 1.15]
    lo = [r for r in rows if r["ratio"] < 0.85]
    print(f"\nOurs more than 15% ABOVE AquaCrop at the pick: {len(hi)}/{len(rows)}; more than 15% BELOW: {len(lo)}/{len(rows)}")


def run_quantity(cities, cache, crops=None):
    crops = crops or list(AC_CROPS)
    print("AquaCrop crop files: " + ", ".join(f"{k}={AC_CROPS[k]}" for k in crops))
    combos = [(c, k) for c in cities for k in crops]
    all_cands = {}
    for i, (city, crop_key) in enumerate(combos, 1):
        print(f"[{i}/{len(combos)}] {city} {crop_key} ...", flush=True)
        all_cands[(city, crop_key)], _ok = build_candidates(city, crop_key, cache)
    print_quantity_report(all_cands)


def run_detail(city, crop_key, cache):
    cands, replica_ok = build_candidates(city, crop_key, cache)
    print(f"Replica check: recomputed ETc matches the production value in {replica_ok}/{len(cands)} candidates.")
    result = analyse(cands)
    if result is None:
        print("Too few dates with an AquaCrop result to compare.")
        return
    print_detail(city, crop_key, cands, result)


def run_summary(cities, cache, crops=None):
    crops = crops or list(AC_CROPS)
    print("AquaCrop crop files: " + ", ".join(f"{k}={AC_CROPS[k]}" for k in crops))
    results, replica_total, cand_total, all_cands = {}, 0, 0, {}
    combos = [(c, k) for c in cities for k in crops]
    for i, (city, crop_key) in enumerate(combos, 1):
        print(f"[{i}/{len(combos)}] {city} {crop_key} ...", flush=True)
        cands, ok = build_candidates(city, crop_key, cache)
        all_cands[(city, crop_key)] = cands
        replica_total += ok
        cand_total += len(cands)
        res = analyse(cands)
        if res is not None:
            results[(city, crop_key)] = res

    print(f"\nReplica check: recomputed ETc matched production in {replica_total}/{cand_total} candidates. "
          f"AquaCrop runs that failed or gave no yield: {FAILED_AQUACROP_RUNS}.")
    print(f"\nAgreement with AquaCrop across {len(results)} city x crop combinations "
          f"(regret = shortfall in AquaCrop water productivity vs its best date in the same pool)")
    print(f"\n{'rule':<26}{'median regret':>14}{'mean':>8}{'worst':>8}{'within 5%':>11}{'yield regret (median)':>23}{'Spearman (median)':>19}")
    print("-" * 109)
    for name, _s, _k in RULES:
        wp = [r["rules"][name]["wp_regret"] for r in results.values()]
        yr = [r["rules"][name]["y_regret"] for r in results.values()]
        sp = [r["rules"][name]["spearman"] for r in results.values() if r["rules"][name]["spearman"] == r["rules"][name]["spearman"]]
        print(f"{name:<26}{median(wp):>14.1%}{mean(wp):>8.1%}{max(wp):>8.1%}"
              f"{sum(1 for x in wp if x <= 0.05):>8}/{len(wp):<2}{median(yr):>23.1%}{median(sp) if sp else float('nan'):>19.2f}")

    print(f"\nBy crop (median WP regret):")
    print(f"{'crop':<16}" + "".join(f"{short:>10}" for _n, short, _k in RULES))
    for crop_key in AC_CROPS:
        row = [r for (c, k), r in results.items() if k == crop_key]
        if row:
            print(f"{crop_key:<16}" + "".join(f"{median([r['rules'][n]['wp_regret'] for r in row]):>10.1%}" for n, _s, _k in RULES))

    n = len(results)
    print("\nDate agreement: how close each rule's start date is to AquaCrop's best-WP date")
    print(f"{'rule':<26}{'same date':>11}{'within 10 d':>13}{'within 20 d':>13}")
    for name, _s, _k in RULES:
        gaps = [circ_days(r["rules"][name]["pick"]["start_doy"], r["best_wp"]["start_doy"]) for r in results.values()]
        print(f"{name:<26}{sum(g == 0 for g in gaps):>8}/{n:<2}{sum(g <= 10 for g in gaps):>10}/{n:<2}"
              f"{sum(g <= 20 for g in gaps):>10}/{n:<2}")

    print("\nNear-optimal window: the contiguous block of eligible dates around the per-day pick whose water per day")
    print("is within X% of the per-day minimum. Does it contain AquaCrop's best-WP date? How many candidate dates")
    print("(10 days apart) does it hold? 'Worst date inside' = the lowest AquaCrop WP among the window's dates,")
    print("as a shortfall vs AquaCrop's best.")
    rows5 = []
    for tol in (0.02, 0.05, 0.10):
        covered, widths, shortfalls = 0, [], []
        for (city, crop_key), r in results.items():
            window = contiguous_window(r["valid_cands"], r["rules"]["per-day (current)"]["pick"], tol)
            widths.append(len(window))
            covered += any(c is r["best_wp"] for c in window)
            shortfalls.append(1 - min(c["ac_wp"] for c in window) / r["best_wp"]["ac_wp"])
            if tol == 0.05:
                rows5.append((shortfalls[-1], city, crop_key, window, r["best_wp"]))
        print(f"  within {tol:>4.0%}: contains AquaCrop's best date in {covered}/{n}; "
              f"window holds median {median(widths):.0f} dates (max {max(widths)}); "
              f"worst date inside: median {median(shortfalls):.1%}, max {max(shortfalls):.1%}")

    print("\nWindows (5% tolerance) whose worst date falls furthest below AquaCrop's best:")
    for short, city, crop_key, window, best in sorted(rows5, key=lambda x: -x[0])[:6]:
        worst = min(window, key=lambda c: c["ac_wp"])
        print(f"  {city:<9}{crop_key:<14}window [{', '.join(c['start'] for c in window)}]")
        print(f"{'':<23}worst date {worst['start']}: WP {worst['ac_wp']:.2f} vs best {best['ac_wp']:.2f} "
              f"({short:.1%} below), mid-season exceedance H/C {worst['mid_heat']}/{worst['mid_cold']}")

    for name, _s, _k in RULES:
        print(f"\nWorst combinations for: {name}")
        ranked = sorted(results.items(), key=lambda kv: -kv[1]["rules"][name]["wp_regret"])[:3]
        for (city, crop_key), r in ranked:
            p = r["rules"][name]["pick"]
            b = r["best_wp"]
            print(f"  {city:<9}{crop_key:<14}picks {p['start']} ({p['days']} d, WP {p['ac_wp']:.2f}); "
                  f"AquaCrop best {b['start']} ({b['days']} d, WP {b['ac_wp']:.2f})  regret {r['rules'][name]['wp_regret']:.1%}")

    print_guard_report(all_cands)
    print_quantity_report(all_cands)


def main():
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cache = {}
    crops = None
    for f in flags:
        if f.startswith("--potato="):          # e.g. --potato=PotatoLocalGDD (a longer-cycle AquaCrop potato)
            AC_CROPS["Potato"] = f.split("=", 1)[1]
        elif f.startswith("--only="):           # e.g. --only=potato (run one crop, about 1/3 of the time)
            crops = [ALIASES[f.split("=", 1)[1].lower()]]
    if "--quantity" in flags:
        cities = QUICK_CITIES if "--quick" in flags else tuple(KNOWN_LOCATIONS)
        run_quantity(cities, cache, crops)
    elif "--guards" in flags:
        cities = QUICK_CITIES if "--quick" in flags else tuple(KNOWN_LOCATIONS)
        run_guards(cities, cache, crops)
    elif "--summary" in flags:
        cities = QUICK_CITIES if "--quick" in flags else tuple(KNOWN_LOCATIONS)
        run_summary(cities, cache, crops)
    else:
        city = args[0].lower() if args else "najran"
        crop_key = ALIASES.get(args[1].lower(), args[1]) if len(args) > 1 else "Corn_(maize)"
        run_detail(city, crop_key, cache)


if __name__ == "__main__":
    main()