"""
Checks heatmap/evapotranspiration.py against the worked examples printed in FAO Irrigation and Drainage Paper 56,
Chapter 4 (https://www.fao.org/4/X0490E/x0490e08.htm). Every input and every expected value below is copied from
that chapter; the code is only asked to reproduce them.

    Example 17  Bangkok, April, monthly means  (13.73 N, 2 m)        ETo = 5.72 mm/day
    Example 18  Uccle (Brussels), 6 July, daily (50.80 N, 100 m)     ETo = 3.88 mm/day
    Example 20  near Lyon, July, only Tmax/Tmin known (45.72 N, 200 m) ETo = 4.56 mm/day

Run from anywhere:   python research/test_et0_fao_examples.py     (exits non-zero if any check fails)
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "heatmap"))
import evapotranspiration as et

failures = []

def check(label, got, expected, tol):
    ok = abs(got - expected) <= tol
    print(f"  {'ok  ' if ok else 'FAIL'} {label:<34} code {got:8.3f} | FAO {expected:8.3f} | tolerance {tol}")
    if not ok:
        failures.append(label)

def tdew_from_ea(ea):
    """Dewpoint (C) whose saturation vapour pressure equals ea (FAO-56 Eq. 14 inverted); the code takes a dewpoint."""
    x = math.log(ea / 0.6108)
    return 237.3 * x / (17.27 - x)

def ea_from_rh(tmax, tmin, rh_max, rh_min):             # FAO-56 Eq. 17
    return (et.saturation_vapor_pressure(tmin) * rh_max / 100 + et.saturation_vapor_pressure(tmax) * rh_min / 100) / 2

print("Example 17: Bangkok, April, monthly data (soil heat flux G = 0.14 as printed by FAO)")
tmax, tmin, ea, u2, lat, z = 34.8, 25.6, 2.85, 2.0, 13.73, 2
rs = 22.65                                              # FAO: Rs = (0.25 + 0.50 * 0.69) * 38.06
check("Ra  (MJ/m2/day)", et.extraterrestrial_radiation(lat, et.MID_MONTH_DAY["APR"]), 38.06, 0.02)
check("delta (kPa/C)", et.slope_vapor_pressure_curve(30.2), 0.246, 0.001)
check("gamma (kPa/C)", et.psychrometric_constant(z), 0.0674, 0.0001)
check("es (kPa)", (et.saturation_vapor_pressure(tmax) + et.saturation_vapor_pressure(tmin)) / 2, 4.42, 0.01)
check("Rn  (MJ/m2/day)", et.net_radiation(tmax, tmin, rs, ea, et.extraterrestrial_radiation(lat, 105), z), 14.33, 0.03)
check("ETo (mm/day)", et.penman_monteith_et0(30.2, tmax, tmin, tdew_from_ea(ea), u2, rs, z, lat, "APR", soil_heat_flux_mj=0.14), 5.72, 0.03)

print("Example 18: Uccle (Brussels), 6 July, daily data (wind 10 km/h measured at 10 m)")
tmax, tmin, lat, z, doy = 21.5, 12.3, 50.80, 100, 187
ea = ea_from_rh(tmax, tmin, 84, 63)
u2 = et.wind_speed_2m(10 / 3.6)                         # 10 km/h = 2.78 m/s at 10 m
rs = 22.07                                              # FAO: Rs = (0.25 + 0.50 * 0.57) * 41.09
check("Ra  (MJ/m2/day)", et.extraterrestrial_radiation(lat, doy), 41.09, 0.02)
check("u2 at 2 m (m/s)", u2, 2.078, 0.005)
check("ea (kPa)", ea, 1.409, 0.002)
check("delta (kPa/C)", et.slope_vapor_pressure_curve((tmax + tmin) / 2), 0.122, 0.001)
check("gamma (kPa/C)", et.psychrometric_constant(z), 0.0666, 0.0001)
check("Rn  (MJ/m2/day)", et.net_radiation(tmax, tmin, rs, ea, et.extraterrestrial_radiation(lat, doy), z), 13.28, 0.03)
check("ETo (mm/day)", et.penman_monteith_et0_doy((tmax + tmin) / 2, tmax, tmin, tdew_from_ea(ea), u2, rs, z, lat, doy), 3.88, 0.03)

print("Example 20: near Lyon, July, missing data (Tdew = Tmin, u2 = 2 m/s, Rs = 0.55 Ra)")
tmax, tmin, lat, z, doy = 26.6, 14.8, 45.72, 200, 196
ra = et.extraterrestrial_radiation(lat, doy)
check("Ra  (MJ/m2/day)", ra, 40.55, 0.02)
check("Rs  (MJ/m2/day)", 0.55 * ra, 22.29, 0.02)
check("ETo (mm/day)", et.penman_monteith_et0_doy((tmax + tmin) / 2, tmax, tmin, tmin, 2.0, 0.55 * ra, z, lat, doy), 4.56, 0.03)

print()
if failures:
    print(f"{len(failures)} check(s) FAILED: {failures}")
    sys.exit(1)
print("All checks passed: the ET0 code reproduces FAO-56 Examples 17, 18 and 20.")
