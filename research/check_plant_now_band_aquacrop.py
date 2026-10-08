"""
Does the app's "Good time to plant" band hold up against AquaCrop?

The Plan tab calls a date "Good time to plant" when it is within 10 days of the crop's best start (one step of the
10-day grid). This asks: for every city x crop that has AquaCrop results (33 combinations), how good is AquaCrop's
water productivity (WP) and yield on the dates INSIDE that band, compared with AquaCrop's best date?

Shortfall = 1 - (AquaCrop value on the date / AquaCrop's best value). Two references:
    all viable dates   the strict one: AquaCrop's best anywhere in the year
    candidate pool     the rule's own pool (shock-free dates if any exist), as in aquacrop_reference_check.py --summary

Reuses the cached AquaCrop results from research/aquacrop_reference_check.py (research/cache/aquacrop_cache.json), so it is
fast once --summary has been run. If the cache is missing it recomputes (about 10 minutes).

Run from the repo root:   python research/check_plant_now_band_aquacrop.py [--all]      (--all prints every combination)
"""
import sys
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aquacrop_reference_check as arc

BAND_DAYS = 10          # the app's "Good time to plant" band: within one step of the best start
PICK_RULE = "per-day (current)"


def band_stats(cands, band_days=BAND_DAYS):
    """AquaCrop shortfalls on the pick and on the worst date inside the band, for one city x crop."""
    res = arc.analyse(cands)
    if res is None:
        return None
    pick = res["rules"][PICK_RULE]["pick"]
    valid_all = [c for c in cands if "ac_wp" in c]
    best_wp_all = max(c["ac_wp"] for c in valid_all)
    best_y_all = max(c["ac_yield"] for c in valid_all)
    best_wp_pool = res["best_wp"]["ac_wp"]
    band = [c for c in valid_all if arc.circ_days(c["start_doy"], pick["start_doy"]) <= band_days]
    wp_all = lambda c: 1 - c["ac_wp"] / best_wp_all
    wp_pool = lambda c: 1 - c["ac_wp"] / best_wp_pool
    worst = max(band, key=wp_all)
    return {"pick": pick, "band": band, "pick_all": wp_all(pick), "pick_pool": wp_pool(pick),
            "worst": worst, "worst_all": wp_all(worst), "worst_pool": max(wp_pool(c) for c in band),
            "worst_yield_short": max(1 - c["ac_yield"] / best_y_all for c in band), "best_wp_all": best_wp_all, "best_y_all": best_y_all}


def share(values, limit):
    return f"{sum(v <= limit for v in values)}/{len(values)}"


def main():
    show_all = "--all" in sys.argv
    weather_cache, rows, skipped = {}, [], []
    combos = [(city, crop) for city in arc.KNOWN_LOCATIONS for crop in arc.AC_CROPS]
    for i, (city, crop) in enumerate(combos, 1):
        print(f"[{i}/{len(combos)}] {city} {crop} ...", flush=True)
        cands, _ = arc.build_candidates(city, crop, weather_cache)
        s = band_stats(cands)
        (rows.append((city, crop, s)) if s else skipped.append((city, crop)))
    n = len(rows)
    print(f"\n{n} city x crop combinations with AquaCrop results" + (f" (skipped: {skipped})" if skipped else ""))
    print(f"Band = dates within {BAND_DAYS} days of the app's best start. Shortfall = how far below AquaCrop's best.\n")
    for label, key_pick, key_worst in (("vs AquaCrop's best among ALL viable dates (strict)", "pick_all", "worst_all"),
                                       ("vs AquaCrop's best inside the rule's own candidate pool", "pick_pool", "worst_pool")):
        p, w = [r[2][key_pick] for r in rows], [r[2][key_worst] for r in rows]
        print(label)
        print(f"  at the pick itself:        median {median(p):5.1%} | mean {mean(p):5.1%} | worst {max(p):5.1%} | within 5%: {share(p, .05)}")
        print(f"  worst date inside the band: median {median(w):5.1%} | mean {mean(w):5.1%} | worst {max(w):5.1%} | "
              f"within 5%: {share(w, .05)} | within 10%: {share(w, .10)} | within 25%: {share(w, .25)}")
    print("\nBy crop, worst date inside the band (strict reference), median:")
    for crop in arc.AC_CROPS:
        w = [r[2]["worst_all"] for r in rows if r[1] == crop]
        if w:
            print(f"  {crop:<14} {median(w):5.1%}   (worst {max(w):5.1%}, n={len(w)})")
    yl = [r[2]["worst_yield_short"] for r in rows]
    print(f"\nYield on the worst band date vs AquaCrop's best yield: median shortfall {median(yl):.1%}, worst {max(yl):.1%}")

    ordered = sorted(rows, key=lambda r: -r[2]["worst_all"])
    print(f"\n{'Every combination' if show_all else 'Eight worst combinations'} (strict reference):")
    print(f"  {'city':<9}{'crop':<14}{'app pick':<9}{'band dates':<26}{'worst date':<11}{'WP short':>9}{'yield short':>12}  mid-season exceedance H/C (that date)")
    for city, crop, s in (ordered if show_all else ordered[:8]):
        w = s["worst"]
        print(f"  {city:<9}{crop:<14}{s['pick']['start']:<9}{', '.join(c['start'] for c in sorted(s['band'], key=lambda c: c['start_doy'])):<26}"
              f"{w['start']:<11}{s['worst_all']:>9.1%}{1 - w['ac_yield'] / s['best_y_all']:>12.1%}"
              f"  {w['mid_heat']}/{w['mid_cold']} of {w['mid_days']} days")


if __name__ == "__main__":
    main()
