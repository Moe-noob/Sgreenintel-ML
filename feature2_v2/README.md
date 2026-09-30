# Feature 2 v2: KSA crop water planner

A stronger, better-evidenced version of Feature 2 (the location-based crop advisor). For any Saudi location it answers, per crop:

- **When can I sow here, and which day is best?** Every one of the 365 days is tested.
- **How long is the season here?** Total and per FAO-56 growth stage. It is longer in cool places like Abha and winter Tabuk, and matches FAO-56 in warm Tihama.
- **How much water per stage, per month and per season?** Net crop water use (ETc) and the gross amount to pump after system efficiency and salt leaching. Given in mm, m³/ha and litres per plant.
- **How often to irrigate?** Root-zone water balance per stage, for your soil.

Everything is self-contained in this folder and runs **offline** (no API keys, no internet). The v1 code in `heatmap/` is untouched. **To remove v2, delete the `feature2_v2/` folder.** Nothing else in the repo imports it.

```bash
pip install openpyxl                 # only needed to re-extract data from the workbook
python feature2_v2/advisor.py riyadh                       # all crops for Riyadh
python feature2_v2/advisor.py jazan --crop tomato --ecw 2.0 --spacing 1.2 0.4
python feature2_v2/advisor.py 26.0 44.0 --soil sandy_loam --method sprinkler
python feature2_v2/report.py         # rebuild outputs/report.html + summary CSV (~30 s)
python -m unittest discover feature2_v2/tests -v           # evidence suite (22 tests)
```

Open `outputs/report.html` in any browser for the interactive report: city picker, sowing calendar, stage table, daily and monthly water charts, in light or dark mode. `outputs/summary_11_cities.csv` has one row per city × crop.

---

## What is better than v1

| | v1 (`heatmap/`) | v2 (this folder) |
|---|---|---|
| Climate data | NASA POWER reanalysis (0.5° grid), needs internet | **FAOCLIM-2 ground stations** (FAO), as fitted and published by Elnesr & Alazba (2016). 24 stations inside KSA, offline |
| ET0 | computed from reanalysis radiation/wind | **FAO's own station Penman-Monteith ET0** |
| Crops | 5 annuals + 2 perennials (strawberry unresolved) | **24 crop seasons, 22 crops** grown in KSA, incl. autumn and spring tomato, okra, molokhia, onion, garlic, melons |
| Paper method | "adapted from" Elnesr & Alazba | **exact reproduction**, checked against the KSU spreadsheet's own computed values (all 365 rows × 21 columns, zero difference) |
| Season length | GDD tables from Paredes 2025 | Paper Eq. 7 heat-unit requirement with the crop's own base/optimum temperatures, so stages stretch in cool climates |
| Stress check | day counts | **degree-days** beyond crop tolerance over the whole season, so a 44 °C day weighs more than a 36 °C one |
| Water output | ETc only | ETc, dry-air upper bound, **gross irrigation** (drip/sprinkler/surface efficiency), **salinity leaching and expected yield loss**, **irrigation interval**, **monthly volumes**, litres per plant |
| Location | 11 cities | 11 cities or any lat/lon (nearest station, with distance and elevation warnings) |

## Evidence

Run `python -m unittest discover feature2_v2/tests -v`. All 22 tests pass.

**A. The published KSU model is reproduced exactly.**
The workbook that ships with the paper (`data/sources/…mmc1.xlsx`) contains Excel's cached results on its `Model` sheet. `elnesr_model.py` recomputes all 365 sowing days from the same inputs. For every column (Tmax, Tmin, ET0, GDD, seasonal HU and ET by summation and by integral, the three suitability flags, the ET/HU/combined indices), the difference is **0 to 9 decimal places**. The heat-unit windows (DOY 90–123 and 199–232), the heat-unit + temperature windows (102–123, 199–232), the day counts (68, 56) and the best day (DOY 199) are also identical.

Reproducing the workbook surfaced these details of how it actually computes, which the Python engine follows exactly:
- The season length is the `DurTherm` column, not `DUR_total`.
- The HU test is `HU_min < HU ≤ HU_max`.
- The temperature test only checks the sowing day.
- `Model!L27` contains a broken `#REF!`, so Excel falls back to `Ta = (Tx+Tn)/2`.
- Paper Eq. 12 prints `(a_E − Tb)` where the sheet correctly uses `a_E`.
- Paper Eq. 28 calls the overall efficiency a *product*, but every value in its Tables 1–2 is the *mean* of the three partial efficiencies.

**B. The paper's model-efficiency metric is reproduced.** Given the relative set sizes in the paper's Table 1 (Central Maryland), `overlap_efficiency()` returns the published overall efficiencies to within 1 %. So once published MEWA or extension sowing calendars are available, you can score this model against them the same way the paper did.

**C. FAO worked examples.** FAO-56 Example 28 (Kc curve, Eq. 66), Example 27 (Kc_mid climate adjustment, Eq. 62: 1.30 and 1.07), FAO-29 Eq. 7 (leaching), Maas–Hoffman yield response, and the FAO-56 p-adjustment limits.

**D. Data integrity.**
- The workbook labels 33 stations "Saudi Arabia", but 9 are actually in Kuwait, Bahrain or Jordan (e.g. "Kuwait International Airport", "Azraq", "Wadi Rum"). They are removed with a point-in-polygon test against `data/geo/national_border/SAU-geo.json`.
- The workbook's trailing column-index row, which would otherwise overwrite crop #1 (Broccoli), is skipped.
- Every station's climate is checked to be physical.

**E. Behaviour and agreement with KSA practice.**
- At a constant optimum temperature the model reproduces FAO-56 stage lengths exactly (tomato 30/40/40/25).
- Cooler weather gives a longer season, and heat above the optimum does not shorten it.
- Against well-established Saudi practice: Tihama (Jazan) tomato is best sown in the mild winter; Asir (Abha) tomato in spring; potato, lettuce, carrot, onion and garlic in Riyadh, Qassim and Madinah are never sown in May–July; Riyadh potato is recommended.

### Sample results (drip, loamy sand, fresh water)

| City | Crop (FAO-56 row) | Status | Best sowing | Harvest | Days | Net m³/ha | Gross m³/ha |
|---|---|---|---|---|---|---|---|
| Riyadh | Potato (semi-arid) | recommended | Nov 16 | Mar 24 | 129 | 3,706 | 4,117 |
| Riyadh | Lettuce (arid, Oct/Nov) | recommended | Nov 16 | Mar 01 | 106 | 2,681 | 2,979 |
| Riyadh | Watermelon (Near East desert) | recommended | Mar 27 | Jun 27 | 93 | 5,199 | 5,776 |
| Riyadh | Tomato (arid, Jan) | possible, with temperature risk | Feb 14 | Jul 13 | 150 | 8,962 | 9,958 |
| Jeddah | Tomato (arid, Jan) | recommended | Oct 09 | Feb 21 | 136 | 5,574 | 6,193 |
| Jazan | Tomato (arid, Jan) | recommended | Dec 08 | Apr 21 | 135 | 4,546 | 5,051 |
| Abha | Potato (semi-arid) | recommended | Oct 11 | Mar 04 | 145 | 4,259 | 4,732 |
| Tabuk | Watermelon (Near East desert) | recommended | Jun 20 | Sep 10 | 83 | 5,382 | 5,980 |

Across all 11 cities × 24 crop seasons: 107 recommended, 144 possible with temperature risk, 13 not suitable (too cold to finish in time). Inland open-field tomato is flagged as risky everywhere. That is consistent with how much of it is grown under protection in central and northern KSA.

---

## Method (in one page)

1. **Climate** (`climate.py`): `X(j) = a + ρ sin(ωj + φ)` for Tmax, Tmin and ET0 (paper Eq. 4), with parameters from the workbook's `Stations` sheet (FAOCLIM-2 long-term means). The nearest station to the location is used, with a warning beyond 100 km or ±300 m elevation.
2. **Heat units and season length** (`season.py`): the daily rate is `min(max(Ta − Tbase, 0), Topt − Tbase)`. The crop needs `(Topt − Tbase) × DUR_total` (paper Eq. 7, the workbook's `ThermN` column). Each FAO-56 stage ends when its share has accumulated.
3. **Water** (`season.py`, `irrigation.py`):
   - Crop water use: `ETc = Kc × ET0`, with Kc from the FAO-56 Eq. 66 curve.
   - Dry-air upper bound: FAO-56 Eq. 62/65 at RHmin 20 %.
   - Gross irrigation: `gross = ETc / (Ea × (1 − LR))`. Ea is 90/75/60 % for drip/sprinkler/surface (FAO Training Manual 4). LR is the FAO-29 leaching requirement.
   - Irrigation interval: `RAW / ETc`, where `RAW = p × 1000 (θFC − θWP) Zr` (FAO-56 Ch. 8, Tables 19 and 22).
4. **Sowing-date choice** (`advisor.py`):
   - A date qualifies if the crop finishes within `DUR_total × (1 + Htol/100)` days, i.e. the paper's heat tolerance applied to duration.
   - The best date has the fewest stress degree-days over the whole season, and among those the lowest seasonal ETc (the paper's minimum-water rule).
   - "Recommended" means stress ≤ 5 °C·days for the whole season.
   - The exact paper result is printed alongside for comparison.

Why the paper's heat-unit test is not used as a hard gate: it requires the mean temperature over `DurTherm` to reach `Topt`, which rejects warm-season crops in the highlands altogether (e.g. every tomato date in Abha). The paper itself reports that `Topt` had to be hand-tuned for 24 of 34 crops in its own validation.

## Sources

- Elnesr, M.N. & Alazba, A.A. (2016). A spreadsheet model to select vegetables planting dates for maximum yield and water use efficiency. *Computers and Electronics in Agriculture* 124:55–64 (King Saud University), and its Appendix A workbook. Supplies all crop rows, cardinal temperatures, heat tolerances and station climate fits.
- FAO (2001). FAOCLIM-2 world-wide agroclimatic database.
- Allen, Pereira, Raes & Smith (1998). FAO-56. Equations 58, 62, 65, 66; Tables 11, 12, 19 and 22.
- Paredes et al. (2025). *Agricultural Water Management* 319:109758. The GDD cutoff form.
- Ayers & Westcot (1985). FAO-29 rev.1, water quality for agriculture. Leaching requirement and salt tolerance (after Maas & Hoffman 1977; Maas 1990 for eggplant and muskmelon).
- Brouwer et al. (1989). FAO Irrigation Water Management Training Manual 4. Field application efficiencies.

`data/*.json` is machine-extracted from the workbook by `build_data.py`, so it is auditable and regenerable. The constants in `agronomy.py` (salt tolerance, rooting depth, soil water, efficiencies) were transcribed by hand from the FAO tables named beside each value. Check them against the source PDFs before quoting them in the report.

## Limitations

- Long-term means are not weather. Single hot or cold days exceed the curves, so stress is a *lower bound*. For live conditions, Feature 3 (Open-Meteo forecast) is the right tool.
- Open-field crops only. Greenhouse, net-house and mulched production are outside the paper's scope.
- Rainfall is ignored, which is conservative (most of KSA gets under 100 mm a year).
- The dry-air Kc bound fits inland stations. Coastal stations (Jeddah, Jazan, Dammam) sit nearer the central estimate.
- The workbook has no field maize, date palm, grape or apple rows, so v1 still covers the perennials.
- Salt tolerance or rooting depth is missing for some crops (okra, molokhia, watermelon, lentil…). The output says so rather than guessing.

## Files

| File | Role |
|---|---|
| `build_data.py` | extracts stations, crops and the verification fixture from the workbook |
| `data/` | `stations_ksa.json`, `crops_eln16.json`, `spreadsheet_fixture.json` |
| `climate.py` | station sinusoids, nearest-station lookup, 11-city map |
| `elnesr_model.py` | exact paper/spreadsheet engine + interval-overlap efficiency |
| `crops.py` | which workbook rows represent KSA crops (+ Arabic names) |
| `season.py` | season length, stages, daily Kc/ET0/ETc, stress degree-days |
| `agronomy.py` | FAO-56/FAO-29 constants for soils, roots, salinity, efficiency |
| `irrigation.py` | gross water, leaching, intervals, monthly and per-plant volumes |
| `advisor.py` | sowing-date scan, selection, CLI |
| `report.py`, `report_template.html` | builds `outputs/report.html` and `outputs/summary_11_cities.csv` |
| `api_router.py` | optional FastAPI router (`/v2/advisor/...`), not mounted by default |
| `tests/` | the evidence suite |
