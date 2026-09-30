"""
Agronomic constants that are NOT in the Elnesr & Alazba workbook, used to
turn crop water use (ETc) into an irrigation plan.

Unlike data/*.json (machine-extracted from the workbook by build_data.py),
these tables were transcribed by hand from the cited FAO publications.
Before quoting a number from here in the report, check it against the
source table named next to it.

Sources
-------
[FAO56-T19] Allen et al. (1998) FAO-56, Table 19: soil water at field
            capacity / wilting point (m3/m3) by texture. Midpoints used.
[FAO56-T22] FAO-56 Table 22: max effective rooting depth Zr (m) and soil
            water depletion fraction p for no stress (ETc ~ 5 mm/day).
            Footnote: p may be adjusted as p = p_T22 + 0.04 (5 - ETc),
            limited to 0.1 <= p <= 0.8. FAO-56 notes the smaller Zr values
            may be used for irrigation scheduling -- they are used here,
            which also matches drip-irrigated vegetables in KSA.
[FAO29]     Ayers & Westcot (1985) FAO Irrigation & Drainage Paper 29 rev.1,
            Table 4, after Maas & Hoffman (1977): salinity threshold ECe
            (dS/m) at which yield starts to fall, and slope b (% yield
            loss per dS/m above it). Leaching requirement: Eq. 7
            LR = ECw / (5 ECe - ECw) for surface/sprinkler; for drip (high
            frequency) LR = ECw / (2 max ECe), max ECe = ECe at zero yield.
            Soil ECe ~ 1.5 x ECw at the usual 15-20 % leaching fraction.
[MAAS90]    Maas (1990) "Crop salt tolerance", ASCE Manual 71 (values not in
            FAO-29, e.g. eggplant, muskmelon).
[FAO-TM4]   Brouwer, Prins, Kay & Heibloem (1989) FAO Irrigation Water
            Management Training Manual 4 ("Irrigation scheduling"), Ch. 3:
            indicative field application efficiencies -- surface 60 %,
            sprinkler 75 %, drip 90 %.
"""

SOILS = {  # [FAO56-T19] midpoints: (theta_FC, theta_WP)
    "sand": (0.12, 0.045),
    "loamy_sand": (0.15, 0.065),
    "sandy_loam": (0.23, 0.11),
    "loam": (0.25, 0.12),
    "silt_loam": (0.29, 0.15),
    "clay_loam": (0.32, 0.20),   # FAO-56 T19 "silty clay loam" 0.30-0.37 / 0.17-0.24 used as proxy
    "clay": (0.36, 0.22),
}

IRRIGATION_EFFICIENCY = {"drip": 0.90, "sprinkler": 0.75, "surface": 0.60}   # [FAO-TM4]

# crop key -> (Zr_min, Zr_max, p)   [FAO56-T22]
ROOTING = {
    "Tomato": (0.7, 1.5, 0.40),
    "Sweet peppers {bell}": (0.5, 1.0, 0.30),
    "Potato": (0.4, 0.6, 0.35),
    "Sweet corn": (0.8, 1.2, 0.50),
    "Cucumber {Fresh Market}": (0.7, 1.2, 0.50),
    "EggPlant": (0.7, 1.2, 0.45),
    "Onions {dry}": (0.3, 0.6, 0.30),
    "Lettuce": (0.3, 0.5, 0.30),
    "Carrots": (0.5, 1.0, 0.35),
    "Spinach": (0.3, 0.5, 0.20),
    "Squash": (0.6, 1.0, 0.50),
    "Zucchini": (0.6, 1.0, 0.50),
    "Watermelon": (0.8, 1.5, 0.40),
    "Sweet Melons": (0.8, 1.5, 0.40),
    "Cabbage": (0.5, 0.8, 0.45),
    "Cauliflower": (0.4, 0.7, 0.45),
    "Broccoli": (0.4, 0.6, 0.45),
    "Beans, green": (0.5, 0.7, 0.45),
    "Radish": (0.3, 0.5, 0.30),
    "Lentil": (0.6, 0.8, 0.50),
    "Garlic": (0.3, 0.5, 0.30),
}

# crop key -> (ECe threshold dS/m, slope %/(dS/m), source)
SALT_TOLERANCE = {
    "Tomato": (2.5, 9.9, "FAO29"),
    "Sweet peppers {bell}": (1.5, 14.0, "FAO29"),
    "Potato": (1.7, 12.0, "FAO29"),
    "Sweet corn": (1.7, 12.0, "FAO29"),
    "Cucumber {Fresh Market}": (2.5, 13.0, "FAO29"),
    "EggPlant": (1.1, 6.9, "MAAS90"),
    "Onions {dry}": (1.2, 16.0, "FAO29"),
    "Lettuce": (1.3, 13.0, "FAO29"),
    "Carrots": (1.0, 14.0, "FAO29"),
    "Spinach": (2.0, 7.6, "FAO29"),
    "Zucchini": (4.7, 9.4, "FAO29"),
    "Sweet Melons": (1.0, 8.4, "MAAS90 (muskmelon)"),
    "Cabbage": (1.8, 9.7, "FAO29"),
    "Broccoli": (2.8, 9.2, "FAO29"),
    "Beans, green": (1.0, 19.0, "FAO29"),
    "Radish": (1.2, 13.0, "FAO29"),
}

# Root depth at sowing/transplanting (FAO-56 Ch. 8: 0.15-0.20 m in the
# initial period); grows linearly to Zr at the start of mid-season.
ZR_INITIAL_M = 0.20


def adjusted_p(p_table, etc_mm_day):
    """FAO-56 Table 22 footnote."""
    return min(0.8, max(0.1, p_table + 0.04 * (5.0 - etc_mm_day)))


def leaching_requirement(crop_key, ecw_ds_m, method):
    """FAO-29 Eq. 7 (surface/sprinkler) or the drip form. Returns (LR, note)."""
    if ecw_ds_m is None or ecw_ds_m <= 0:
        return 0.0, None
    st = SALT_TOLERANCE.get(crop_key)
    if st is None:
        return 0.0, "no FAO-29 salt-tolerance value for this crop; leaching not computed"
    thr, slope, _ = st
    if method == "drip":
        max_ece = thr + 100.0 / slope
        lr = ecw_ds_m / (2.0 * max_ece)
    else:
        denom = 5.0 * thr - ecw_ds_m
        if denom <= 0:
            return None, f"water ECw {ecw_ds_m} dS/m is too saline for full yield of this crop (FAO-29 Eq. 7 undefined)"
        lr = ecw_ds_m / denom
    return min(lr, 0.9), None


def salinity_yield_pct(crop_key, ecw_ds_m):
    """Relative yield (Maas-Hoffman) at soil ECe ~ 1.5 ECw (FAO-29 rule of thumb)."""
    st = SALT_TOLERANCE.get(crop_key)
    if st is None or ecw_ds_m is None:
        return None
    thr, slope, _ = st
    ece = 1.5 * ecw_ds_m
    return max(0.0, min(100.0, 100.0 - slope * max(0.0, ece - thr)))
