"""
Agronomic constants that are NOT in the Elnesr & Alazba workbook, used to
turn crop water use (ETc) into an irrigation plan.

All crop and soil values below are taken from FAO-56 Rev.1 (Pereira, Allen,
Paredes, Lopez-Urrea, Raes, Smith, Kilic & Salman 2025, "Crop
evapotranspiration", FAO Irrigation & Drainage Paper 56 Rev.1,
doi:10.4060/cd6621en; copy at repo root, cd6621en.pdf) and checked line by
line against the text extracted from that PDF. Page numbers are the book's
printed page numbers (PDF page - 32).

Sources
-------
[R1-T6.1]  Table 6.1 (p. 165-167) vegetable Kc ini/mid/end, max height h, max root depth Zr
[R1-T6.2]  Table 6.2 (p. 168-169) field crops (green bean, lentil, sweet maize)
[R1-T6.10] Tables 6.10-6.12 (p. 204-212) growing-degree-day thresholds and stage GDD
[R1-T7.5]  Table 7.5 (p. 232) soil water at field capacity / wilting point; midpoints used
[R1-T8.1]  Table 8.1 (p. 258-259) depletion fraction p, vegetables (for ETc ~ 5 mm/day)
[R1-T8.2]  Table 8.2 (p. 260) depletion fraction p, field crops
[R1-E8.5]  Eq. 8.5 (p. 257) p = p_table + 0.04 (5 - ETc), limited to 0.1-0.8
[R1-T8.8]  Table 8.8 (p. 281) salt tolerance of vegetables: ECe threshold and
           slope b, often as ranges; Table 8.9 (p. 282) field crops
[FAO29]    Ayers & Westcot (1985) FAO-29 rev.1 leaching requirement
           LR = ECw / (5 ECe - ECw) (Eq. 7; restated in FAO-56 Rev.1 Sec. 8)
           for surface/sprinkler; for drip LR = ECw / (2 max ECe), max ECe =
           ECe at zero yield. Soil ECe ~ 1.5 x ECw at 15-20 % leaching fraction.
[FAO-TM4]  Brouwer et al. (1989) FAO Irrigation Water Management Training
           Manual 4: field application efficiencies surface 60 %, sprinkler
           75 %, drip 90 %. (Not in FAO-56; still hand-transcribed.)

Choices
-------
* Zr: the LOWER end of the Table 6.1 range is used (shallower roots ->
  smaller readily available water -> more frequent irrigation), which
  suits drip-irrigated vegetables and errs on the safe side.
* Salinity: where Table 8.8 gives a range, the leaching requirement uses
  the most sensitive end (lower threshold, steeper slope) and the expected
  yield is reported as a range across the table's values.
"""

SOILS = {  # [R1-T7.5] midpoints: (theta_FC, theta_WP)
    "sand": (0.12, 0.045),
    "loamy_sand": (0.15, 0.065),
    "sandy_loam": (0.23, 0.11),
    "loam": (0.25, 0.12),
    "silt_loam": (0.29, 0.15),
    "clay_loam": (0.335, 0.205),   # [R1-T7.5] "silt clay loam" 0.30-0.37 / 0.17-0.24 used as proxy
    "clay": (0.36, 0.22),
}

IRRIGATION_EFFICIENCY = {"drip": 0.90, "sprinkler": 0.75, "surface": 0.60}   # [FAO-TM4]

# crop key -> (Kc ini, Kc mid, Kc end, max height h m, Table 6.1/6.2 row used)   [R1-T6.1], [R1-T6.2]
KC_REV1 = {
    "Tomato": (0.60, 1.10, 1.00, 0.60, "Tomato, fresh market"),
    "Sweet peppers {bell}": (0.60, 1.10, 1.00, 0.70, "Bell pepper"),
    "Potato": (0.50, 1.10, 0.40, 0.60, "Potato, long season"),
    "Cucumber {Fresh Market}": (0.60, 1.00, 0.75, 0.40, "Cucumber, fresh market"),
    "EggPlant": (0.60, 1.05, 0.95, 0.80, "Eggplant"),
    "Onions {dry}": (0.70, 1.05, 0.70, 0.45, "Onions, dry"),
    "Lettuce": (0.70, 1.05, 1.05, 0.35, "Lettuce"),
    "Carrots": (0.70, 1.00, 0.85, 0.30, "Carrots"),
    "Spinach": (0.70, 1.05, 1.00, 0.35, "Spinach"),
    "Squash": (0.50, 1.00, 0.70, 0.50, "Zucchini, squash"),
    "Watermelon": (0.40, 1.05, 0.70, 0.40, "Watermelon"),
    "Sweet Melons": (0.50, 1.00, 0.80, 0.30, "Melon"),
    "Cabbage": (0.70, 1.05, 1.00, 0.40, "Common cabbage"),
    "Cauliflower": (0.70, 1.05, 1.00, 0.40, "Cauliflower"),
    "Broccoli": (0.70, 1.10, 1.10, 0.60, "Broccoli"),
    "Beans, green": (0.50, 1.05, 0.95, 0.60, "Common bean, green (Table 6.2)"),
    "Radish": (0.70, 0.95, 0.85, 0.30, "Radish"),
    "Lentil": (0.40, 1.05, 0.30, 0.50, "Lentil (Table 6.2)"),
    "Okra": (0.50, 0.95, 0.80, 0.90, "Okra"),
    "Sweet corn": (0.30, 1.15, 1.05, 2.00, "Maize, sweet (Table 6.2)"),
    "Garlic": (0.70, 1.05, 0.70, 0.50, "Garlic"),
    "Mulukhiyah": (0.50, 1.05, 0.95, 1.30, "Jute mallow for leaves"),
    "Pumpkin": (0.50, 0.95, 0.70, 0.40, "Pumpkin, winter squash"),
}

# crop key -> (Tbase, Tupper, [stage GDD rows (ini, dev, mid, late)], source)
# Tbase/Tupper: Table 6.10 (p. 204-205). Stage GDD: Table 6.11 (p. 209-210, field observed)
# or Table 6.12 (p. 211-212, derived from the 1998 Table 11). Where two rows are given
# (short/long season, min/max length), the season is simulated with their mean.
REV1_GDD = {
    "Tomato": (7, 28, [(325, 660, 880, 200)], "6.11 Tomato, market"),
    "Sweet peppers {bell}": (10, 35, [(445, 1180, 745, 45)], "6.11 Bell pepper, common"),
    "Potato": (2, 30, [(260, 490, 525, 325), (405, 530, 490, 835)], "6.11 Potato, short & long season"),
    "Onions {dry}": (4.5, 35, [(460, 470, 880, 480)], "6.11 Onions, common"),
    "Lettuce": (4, 28, [(365, 385, 215, 20), (360, 455, 455, 20)], "6.11 Lettuce, short & long season"),
    "Carrots": (6, 30, [(320, 465, 500, 290)], "6.11 Carrots, common"),
    "Garlic": (4, 30, [(150, 340, 335, 315), (580, 615, 315, 240)], "6.11 Garlic, short & long season"),
    "Broccoli": (4.5, 30, [(195, 250, 210, 100), (295, 350, 525, 110)], "6.11 Broccoli, short & long season"),
    "Sweet Melons": (10, 38, [(185, 520, 315, 155), (140, 545, 460, 455)], "6.11 Melon, short & long season"),
    "Sweet corn": (10, 32, [(200, 310, 360, 115), (355, 500, 430, 200)], "6.11 Maize, sweet, short & long season"),
    "Beans, green": (10, 32, [(20, 110, 220, 100), (230, 390, 400, 150)], "6.12 Bean, green, min & max length"),
    "Cabbage": (4.5, 30, [(790, 620, 220, 80)], "6.12 Cabbage, common"),
    "Cauliflower": (4.5, 30, [(700, 610, 200, 60)], "6.12 Cauliflower, common"),
    "Spinach": (4, 25, [(130, 190, 180, 70), (250, 200, 140, 20)], "6.12 Spinach, min & max length"),
    "Cucumber {Fresh Market}": (10, 32, [(80, 170, 450, 270), (370, 510, 520, 120)], "6.12 Cucumber, min & max length"),
    "EggPlant": (10, 35, [(280, 440, 380, 80), (230, 540, 480, 180)], "6.12 Eggplant, min & max length"),
    "Squash": (10, 32, [(90, 200, 210, 130), (160, 370, 360, 260)], "6.12 Squash, Zucchini, min & max length"),
    "Lentil": (2, 35, [(130, 270, 830, 620), (120, 300, 860, 650)], "6.12 Lentil, min & max length"),
    "Pumpkin": (10, 32, [(170, 380, 370, 150), (230, 440, 430, 200)], "6.12 Pumpkin & winter squash, min & max"),
    # Not in Tables 6.11/6.12: watermelon, radish, okra, jute mallow (molokhia) -> Elnesr & Alazba Eq. 7 method.
}

# crop key -> (Zr_min, Zr_max, p)   Zr [R1-T6.1/6.2], p [R1-T8.1/8.2]
ROOTING = {
    "Tomato": (0.60, 1.20, 0.40),
    "Sweet peppers {bell}": (0.50, 1.00, 0.40),
    "Potato": (0.40, 0.60, 0.40),
    "Sweet corn": (0.60, 1.50, 0.50),          # p: Maize (Table 8.2)
    "Cucumber {Fresh Market}": (0.60, 1.20, 0.45),
    "EggPlant": (0.40, 1.00, 0.40),
    "Onions {dry}": (0.30, 0.60, 0.30),
    "Lettuce": (0.30, 0.50, 0.30),
    "Carrots": (0.30, 0.50, 0.30),
    "Spinach": (0.30, 0.50, 0.25),
    "Squash": (0.60, 1.10, 0.45),              # Zucchini, squash
    "Watermelon": (0.80, 1.50, 0.45),
    "Sweet Melons": (0.60, 1.20, 0.40),        # Melon
    "Cabbage": (0.30, 0.50, 0.35),
    "Cauliflower": (0.40, 0.90, 0.40),
    "Broccoli": (0.40, 0.90, 0.40),
    "Beans, green": (0.50, 0.90, 0.45),        # Common bean
    "Radish": (0.30, 0.50, 0.30),
    "Lentil": (0.60, 0.80, 0.50),
    "Okra": (0.60, 0.80, 0.40),
    "Garlic": (0.30, 0.50, 0.30),
    "Mulukhiyah": (0.50, 0.70, 0.40),          # Jute mallow for leaves
    "Pumpkin": (0.90, 1.50, 0.40),             # Pumpkin, winter squash
}

# crop key -> (ECe threshold low, high dS/m, slope b low, high %/(dS/m), Table 8.8/8.9 row)
SALT_TOLERANCE = {
    "Tomato": (0.9, 2.5, 9.0, 9.9, "Tomato"),
    "Sweet peppers {bell}": (1.5, 1.7, 12.0, 14.0, "Bell and chili pepper"),
    "Potato": (1.7, 1.7, 12.0, 12.0, "Potato"),
    "Sweet corn": (1.7, 1.7, 12.0, 12.0, "Maize (Table 8.9)"),
    "Cucumber {Fresh Market}": (1.1, 2.5, 7.0, 13.0, "Cucumber"),
    "EggPlant": (1.1, 1.1, 6.9, 6.9, "Eggplant"),
    "Onions {dry}": (1.2, 1.2, 16.0, 16.0, "Onion"),
    "Lettuce": (1.3, 1.7, 12.0, 13.0, "Lettuce"),
    "Carrots": (1.0, 1.0, 14.0, 14.0, "Carrot"),
    "Spinach": (2.0, 3.2, 7.6, 16.0, "Spinach"),
    "Squash": (4.7, 4.9, 10.0, 10.5, "Squash, Zucchini"),
    "Sweet Melons": (1.0, 1.0, 8.4, 8.4, "Melon"),
    "Cabbage": (1.0, 1.8, 9.8, 14.0, "Cabbage"),
    "Cauliflower": (1.5, 1.8, 6.2, 14.4, "Cauliflower"),
    "Broccoli": (1.3, 2.8, 9.2, 15.8, "Broccoli"),
    "Beans, green": (1.0, 1.0, 19.0, 19.0, "Bean (Table 8.9)"),
    "Radish": (1.2, 2.0, 7.6, 13.0, "Radish"),
    "Garlic": (3.9, 3.9, 14.3, 14.3, "Garlic"),
    "Pumpkin": (1.2, 1.2, 13.0, 13.0, "Pumpkin, winter squash"),
    # Table 8.8 lists okra and watermelon as MS without numbers; lentil and jute mallow are not listed.
}

# Root depth at sowing/transplanting (FAO-56 Ch. 8: 0.15-0.20 m in the
# initial period); grows linearly to Zr at the start of mid-season.
ZR_INITIAL_M = 0.20


def adjusted_p(p_table, etc_mm_day):
    """FAO-56 Rev.1 Eq. 8.5."""
    return min(0.8, max(0.1, p_table + 0.04 * (5.0 - etc_mm_day)))


def leaching_requirement(crop_key, ecw_ds_m, method):
    """FAO-29 Eq. 7 (surface/sprinkler) or the drip form, at the sensitive end of the Table 8.8 range.
    Returns (LR, note)."""
    if ecw_ds_m is None or ecw_ds_m <= 0:
        return 0.0, None
    st = SALT_TOLERANCE.get(crop_key)
    if st is None:
        return 0.0, "FAO-56 Rev.1 Table 8.8 gives no salt-tolerance numbers for this crop; leaching not computed"
    thr, _, _, slope, _ = st
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
    """
    Relative yield range (Maas-Hoffman) at soil ECe ~ 1.5 ECw, across the
    Table 8.8 threshold/slope ranges: {"low": most sensitive, "high": most tolerant}.
    """
    st = SALT_TOLERANCE.get(crop_key)
    if st is None or ecw_ds_m is None:
        return None
    thr_lo, thr_hi, b_lo, b_hi, _ = st
    ece = 1.5 * ecw_ds_m
    y = lambda thr, b: max(0.0, min(100.0, 100.0 - b * max(0.0, ece - thr)))
    return {"low": y(thr_lo, b_hi), "high": y(thr_hi, b_lo)}
