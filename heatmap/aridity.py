"""
Humidity conditioning of dry-site weather data for reference evapotranspiration (ET0).

Why this exists
---------------
FAO-56 Rev.1 (Pereira, Allen, Paredes et al. 2025, doi:10.4060/cd6621en), Sec. 2.5, explains that the FAO
Penman-Monteith ET0 equation assumes weather measured over a well-watered reference grass surface. Weather
data from dry, non-irrigated surroundings -- and gridded/reanalysis data over dry land such as NASA POWER --
carry air that is hotter and DRIER than a reference surface would have. Fed to the equation unchanged, they
overstate ET0. Over Saudi land the NASA minimum temperature exceeds the NASA dewpoint by up to ~27 C on a July
night; FAO's own example of a badly non-reference site shows about 10 C.

The correction (Rev.1 Sec. 2.5.2, Eq. 2.6 and 2.7)
--------------------------------------------------
Keep the measured air temperatures, replace the humidity:

    Tdew = Tmin - aT                                   (Eq. 2.6)

aT is a subtractive factor set by the UNEP aridity index AI = P / CEI_Thornthwaite (Box 2.4):

    AI < 0.05            hyper-arid       aT = 4-6 C   (6 only under very stringent site aridity)
    0.05 <= AI < 0.20    arid             aT = 2-3 C
    0.20 <= AI < 0.50    semi-arid        aT = 1-2 C
    0.50 <= AI < 0.65    dry sub-humid    aT = 0-1 C
    0.65 <= AI           humid            aT = 0

We use the lower end of the hyper-arid range (4 C), the middle of the other ranges (2.5, 1.5, 0.5), and 0 for
humid climates. We also never make the air DRIER than the source says: the conditioned dewpoint is
max(source dewpoint, Tmin - aT). Over the 11 validated cities this differs from the pure formula by at most
0.3 % of annual ET0 (only Abha, which has moist days).

What this does and does not fix
-------------------------------
Over the 11 validated cities it lowers annual ET0 by 6-13 % (median ~12 %), and the seasonal shape barely
changes (summer-to-winter ratio moves ~4 %), so planting-date RANKING is essentially unaffected. It does not
resolve wind speed (NASA 2 m winds of 2.4-3.6 m/s; FAO's default is 2 m/s, which would lower ET0 by another
~8-10 %). Absolute litres and m3/ha therefore remain uncertain by roughly 15 % (our estimate from cross-checks
against station ET0 and Hargreaves).

The same correction must be applied to LIVE data in the tracker (care/tracker.py) or the live-vs-typical
comparison would be inconsistent: use conditioned_dewpoint() with the aT stored on the climatology.

Run `python heatmap/aridity.py` to execute the self-test (FAO-56 Rev.1 Example 2.1, Lerida, AI = 0.52).
"""

MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def thornthwaite_cei(monthly_temps_c):
    """
    Thornthwaite (1948) annual climatic evaporation index as given in Rev.1 Box 2.4.
    Returns (heat_index_I, alpha, CEI_mm). Months with Tmean <= 0 contribute nothing.
    """
    heat_index = sum((t / 5.0) ** 1.514 for t in monthly_temps_c if t > 0)
    if heat_index <= 0:
        return 0.0, 0.0, 0.0
    alpha = 6.75e-7 * heat_index ** 3 - 7.71e-5 * heat_index ** 2 + 1.7912e-2 * heat_index + 0.492
    cei = sum(16.0 * (10.0 * t / heat_index) ** alpha for t in monthly_temps_c if t > 0)
    return heat_index, alpha, cei


def _monthly(clim, field, total=False):
    out, j = [], 0
    for n in MONTH_DAYS:
        seg = [d[field] for d in clim[j:j + n]]
        out.append(sum(seg) if total else sum(seg) / len(seg))
        j += n
    return out


def unep_aridity_index(clim):
    """
    UNEP aridity index from a 365-day climatology (needs temp_c and precip_mm_day).
    Returns (AI, annual_precip_mm, CEI_mm), or None if the inputs are unavailable.
    """
    if len(clim) < 365 or "precip_mm_day" not in clim[0] or "temp_c" not in clim[0]:
        return None
    temps = _monthly(clim, "temp_c")
    precip = sum(p * n for p, n in zip(_monthly(clim, "precip_mm_day"), MONTH_DAYS))
    _, _, cei = thornthwaite_cei(temps)
    if cei <= 0:
        return None
    return precip / cei, precip, cei


def aridity_class(ai):
    if ai < 0.05:
        return "hyper-arid"
    if ai < 0.20:
        return "arid"
    if ai < 0.50:
        return "semi-arid"
    if ai < 0.65:
        return "dry sub-humid"
    return "humid"


def aT_for_index(ai):
    """Subtractive factor aT (deg C) of Rev.1 Eq. 2.6 for an aridity index (see module docstring for the choices)."""
    if ai < 0.05:
        return 4.0
    if ai < 0.20:
        return 2.5
    if ai < 0.50:
        return 1.5
    if ai < 0.65:
        return 0.5
    return 0.0


def conditioned_dewpoint(raw_dewpoint_c, tmin_c, aT_c):
    """Dewpoint to use for ea: Rev.1 Eq. 2.6, but never drier than the source (max of the two)."""
    if not aT_c:
        return raw_dewpoint_c
    return max(raw_dewpoint_c, tmin_c - aT_c)


def condition_climatology(clim):
    """
    Returns (new_clim, info). new_clim is a list of copies of the 365 daily dicts with dewpoint_c conditioned,
    the source value kept as dewpoint_raw_c, and aridity_aT stored on every day (the tracker reads it for live
    data). info = {aridity_index, aridity_class, aT_c, annual_precip_mm, cei_mm}, or None if the aridity index
    cannot be computed (the climatology is then returned unchanged).
    """
    res = unep_aridity_index(clim)
    if res is None:
        return clim, None
    ai, precip, cei = res
    aT = aT_for_index(ai)
    out = []
    for d in clim:
        nd = dict(d)
        nd["dewpoint_raw_c"] = d["dewpoint_c"]
        nd["dewpoint_c"] = conditioned_dewpoint(d["dewpoint_c"], d["temp_min_c"], aT)
        nd["aridity_aT"] = aT
        out.append(nd)
    return out, {"aridity_index": ai, "aridity_class": aridity_class(ai), "aT_c": aT,
                 "annual_precip_mm": precip, "cei_mm": cei}


def _selftest():
    # FAO-56 Rev.1 Example 2.1: Lerida, Spain -> I = 68.89, alpha = 1.58, CEI = 725.26 mm, P = 380 mm, AI = 0.52
    temps = [5.2, 7.1, 11.6, 14.3, 18.3, 22.1, 24.95, 24.6, 21.5, 15.5, 9.45, 5.7]
    precip = [22, 18, 31, 46, 47, 43, 24, 34, 34, 30, 22, 29]
    i, a, cei = thornthwaite_cei(temps)
    ai = sum(precip) / cei
    assert abs(i - 68.89) < 0.1 and abs(a - 1.58) < 0.01 and abs(cei - 725.26) < 2.0 and abs(ai - 0.52) < 0.01, (i, a, cei, ai)
    assert aridity_class(ai) == "dry sub-humid" and aT_for_index(0.52) == 0.5
    # FAO Example 2.2: Lerida (dry sub-humid) uses Tdew = Tmin - 1 -> our class midpoint is 0.5; behaviour check only
    assert conditioned_dewpoint(2.0, 29.0, 4.0) == 25.0          # very dry source air is raised to Tmin - aT
    assert conditioned_dewpoint(26.0, 29.0, 4.0) == 26.0         # air already moister than Tmin - aT is left alone
    assert conditioned_dewpoint(2.0, 29.0, 0.0) == 2.0           # humid climates: no change
    print(f"aridity.py self-test OK: Lerida I={i:.2f} (FAO 68.89), alpha={a:.2f} (1.58), CEI={cei:.1f} mm "
          f"(725.26), AI={ai:.2f} (0.52)")


if __name__ == "__main__":
    _selftest()