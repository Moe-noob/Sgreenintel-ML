# Feature 2 v2: KSA crop water planner

A stronger, better-evidenced version of Feature 2 (the location-based crop advisor). For any Saudi location it answers, per crop:

- **When can I sow here, and which day is best?** Every one of the 365 days is tested. You get a best date and a lowest-risk alternative.
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
python -m unittest discover feature2_v2/tests -v           # evidence suite (24 tests)
python feature2_v2/validation/alsadon2002.py               # benchmark vs Saudi directorate calendars
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

Run `python -m unittest discover feature2_v2/tests -v`. All 24 tests pass.

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

**E. Benchmark against Saudi directorate calendars (Alsadon 2002).**
Alsadon (2002, *J. King Saud Univ.*; copy in `data/sources/alsadon_2002_planting_dates_KSA.doc`) Table 5 lists the sowing dates recommended by the regional Directorates of Agriculture & Water for 16 crop × region cases (Tabuk, Al-Ahsa, Qassim, Jazan). It also lists Alsadon's own heat-unit program dates. `validation/alsadon2002.py` transcribes the table (original Arabic kept) and scores every method against the directorate dates:

| Method | Precision | Recall | Overlap efficiency Ω |
|---|---|---|---|
| Alsadon (2002) heat-unit program | 60 % | 40 % | 54 % |
| Elnesr & Alazba spreadsheet, heat-unit window | 68 % | 36 % | 51 % |
| Elnesr & Alazba spreadsheet, heat units + temperature | 53 % | 7 % | 36 % |
| **v2 "finishes in time" window** | 44 % | **74 %** | **68 %** |
| v2 low-stress window | 64 % | 17 % | 44 % |

- Precision is the share of a method's window that the directorate agrees with (Alsadon's own "% agreement" definition).
- Recall is the share of the directorate's window that the method covers.
- Ω is the paper's Eqs. 19–28 overlap efficiency.
- The directorates publish broad "you can plant" calendars. v2's broad window matches them best; its low-stress window is a conservative subset.

**Best single date inside the directorate window:** v2 10/16, the paper's index alone 11/16, and v2's first-version rule (least stress, then least water) 9/16. The best-date rule was changed *after* seeing this benchmark (no numeric parameter was fitted), so 10/16 is not an independent test.

The variant that tries the paper's heat-units-only index first scores 12/16, but it recommends sowing garlic in Qassim in late July at 43 °C. With 16 cases, 12 vs 10 is within noise, so the rule without that agronomic error was kept.

Where v2 misses:
- Tabuk squash and watermelon: the directorates plant in spring and July, which v2 treats as too cold or too hot.
- Al-Ahsa onion: there is no FAOCLIM station in Al-Ahsa; the nearest is Qatif, about 125 km away.
- Jazan cucumber: the best date is Dec 31, just outside the Sep–Nov and Jan windows.

**F. Behaviour and agreement with KSA practice.**
- At a constant optimum temperature the model reproduces FAO-56 stage lengths exactly (tomato 30/40/40/25).
- Cooler weather gives a longer season, and heat above the optimum does not shorten it.
- Against well-established Saudi practice: Tihama (Jazan) tomato is best sown in the mild winter; Asir (Abha) tomato in spring; potato, lettuce, carrot, onion and garlic in Riyadh, Qassim and Madinah are never sown in May–July; Riyadh potato is recommended.

### Sample results (drip, loamy sand, fresh water)

| City | Crop (FAO-56 row) | Status | Best sowing | Harvest | Days | Gross m³/ha | Lowest-risk date (gross m³/ha) |
|---|---|---|---|---|---|---|---|
| Riyadh | Potato (semi-arid) | recommended | Feb 08 | Jun 10 | 123 | 7,196 | Nov 16 (4,117) |
| Riyadh | Lettuce (arid, Oct/Nov) | recommended | Feb 01 | May 12 | 101 | 4,840 | Nov 16 (2,979) |
| Riyadh | Watermelon (Near East desert) | recommended | Apr 21 | Jul 12 | 83 | 5,804 | Mar 27 (5,776) |
| Riyadh | Tomato (arid, Jan) | possible, with temperature risk | Feb 14 | Jul 13 | 150 | 9,958 | same |
| Jeddah | Tomato (arid, Jan) | recommended | Oct 03 | Feb 15 | 136 | 6,204 | Oct 09 (6,193) |
| Jazan | Tomato (arid, Jan) | recommended | Oct 16 | Feb 27 | 135 | 5,615 | Dec 08 (5,051) |
| Tabuk | Watermelon (Near East desert) | recommended | Jun 20 | Sep 10 | 83 | 5,980 | same |

Across all 11 cities × 24 crop seasons: 108 recommended, 143 possible with temperature risk, 13 not suitable (too cold to finish in time). Inland open-field tomato is flagged as risky everywhere. That is consistent with how much of it is grown under protection in central and northern KSA.

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
   - **Best date:** the paper's optimisation-index day, taken first from its "yellow band" (heat units and sowing-day temperature both OK), else from its heat-units-only band, as long as it qualifies. Otherwise the lowest-risk date is used.
   - **Lowest-risk date:** the fewest stress degree-days over the whole season, and among those the lowest seasonal ETc. It often needs much less water (Riyadh potato: Nov 16, 4,117 m³/ha, vs Feb 08, 7,196 m³/ha).
   - "Recommended" means at least one qualifying date has ≤ 5 °C·days of stress for the whole season.

Why the paper's heat-unit test is not used as a hard gate: it requires the mean temperature over `DurTherm` to reach `Topt`, which rejects warm-season crops in the highlands altogether (e.g. every tomato date in Abha). The paper itself reports that `Topt` had to be hand-tuned for 24 of 34 crops in its own validation.

## Sources

- Alsadon, A.A. (2002). The best planting dates for vegetable crops in Saudi Arabia: compatibility between heat-unit dates and dates suggested by the regional offices of the Ministry of Agriculture and Water. *J. King Saud Univ. (Agric. Sci.)* 14:75–97. Used as the KSA validation benchmark.
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
| `validation/alsadon2002.py` | benchmark vs directorate sowing dates (writes `alsadon2002_results.json`) |
| `tests/` | the evidence suite |
