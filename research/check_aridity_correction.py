"""
Check that the FAO humidity conditioning (FAO-56 Rev.1 Eq. 2.6) behaves on YOUR machine as it did in testing.

For the 11 validated cities it prints the UNEP aridity index, the class and aT used, and annual ET0 before and after
the correction, then compares the "after" value with the one verified in the analysis (tolerance 1.5 %).

Run from the project root, after apply_step12_patch.py:
    python research/check_aridity_correction.py
"""

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

import aridity                                     # noqa: E402
import nasa_power                                  # noqa: E402
from season_simulator import _et0_for              # noqa: E402

CITIES = {
    "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10), "najran": (17.49, 44.13),
    "jazan": (16.89, 42.55), "abha": (18.22, 42.51), "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98),
    "madinah": (24.47, 39.61), "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
}
# Verified in the analysis (NASA normals, site-elevation corrected): annual ET0 mm before / after the correction.
EXPECTED = {
    "riyadh": (2742, 2387), "jeddah": (2979, 2611), "dammam": (2563, 2248), "najran": (2686, 2349),
    "jazan": (2290, 1996), "abha": (1786, 1679), "tabuk": (2509, 2276), "qassim": (2677, 2375),
    "madinah": (3056, 2669), "makkah": (3114, 2685), "hail": (2498, 2171),
}
TOL = 0.015


def annual_et0(clim, elevation_m, lat):
    return sum(_et0_for(d, elevation_m, lat) for d in clim)


def main():
    print(f"{'city':<9}{'AI':>7}  {'class':<11}{'aT':>4}{'before':>8}{'after':>7}{'change':>8}   {'expected after':>14}  result")
    bad = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for city, (lat, lon) in CITIES.items():
            raw, elev, _ = nasa_power.fetch_daily_climatology_full(lat, lon, correct_aridity=False)
            new, elev2, _ = nasa_power.fetch_daily_climatology_full(lat, lon)
            _, info = aridity.condition_climatology(raw)
            before, after = annual_et0(raw, elev, lat), annual_et0(new, elev2, lat)
            exp_before, exp_after = EXPECTED[city]
            ok = abs(before / exp_before - 1) <= TOL and abs(after / exp_after - 1) <= TOL
            bad += not ok
            print(f"{city:<9}{info['aridity_index']:>7.3f}  {info['aridity_class']:<11}{info['aT_c']:>4.1f}{before:>8.0f}{after:>7.0f}"
                  f"{(after / before - 1) * 100:>7.1f}%   {exp_after:>14}  {'PASS' if ok else 'CHECK'}")
    print()
    if bad:
        print(f"{bad} city/cities differ from the verified values by more than {TOL:.1%}. Paste this output so we can look.")
    else:
        print("All 11 cities match the verified values: the humidity correction is working as tested.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())