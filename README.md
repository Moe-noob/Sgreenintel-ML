# SGreen Intel — ML Core

AI-powered agricultural platform for Saudi farmers. Three features: CNN plant disease detection, location-based crop advisor, and smart plant care tracker. Built as a Najran University CS capstone aligned with Saudi Arabia's Vision 2030 Green Initiative.

---

## Features

### Feature 1 — CNN Plant Disease Detection
MobileNetV2-based classifier for 35 disease/healthy classes across 7 crops. Trained on a hybrid lab+field dataset and fine-tuned progressively on real-world photo collections to reduce domain gap. An optional crop selector lets the user narrow the search to one crop's own classes before the model answers.

**Crops covered:** Tomato, Potato, Bell Pepper, Grape, Apple, Corn, Strawberry

**Final model (v6p2), on a frozen, de-duplicated benchmark** (`feature1_eval/`; 1,267 PlantDoc + PlantWild test photos pooled across 24 of the 35 classes; see `DEFENSE_PREP.md` for the method and what the other 11 classes lack):
- Model guesses the crop (all 35 classes compete): **67.0%** accuracy (95% CI 64.6-69.7%)
- User names the crop first (only that crop's classes compete; no retraining): **76.5%** accuracy (95% CI 74.3-78.9%) — about **+10 points**, the single largest accuracy gain found for Feature 1 so far
- On photos confirmed to have no near-duplicate in v1's own training data, the same two figures are 65.3% and 75.2% — the fairer estimate of accuracy on truly unseen photos
- PlantVillage (lab) test set: **95.44%** — domain gap to the real-world benchmark above is about **28-30 points**, not the 23pp figure previously reported, which mixed two different models' numbers (see `DEFENSE_PREP.md`)
- Weakest crop: tomato (56.1%, the largest single crop in the benchmark); strongest: grape (93.3%)

### Feature 2 — Location-Based Crop Advisor
Planting-date and water-budget simulation for **11 validated Saudi cities** (and any other Saudi location by search or geolocation) for **14 annual crops plus grape and apple**. For each crop it reports **two planting seasons** (an autumn pick and a spring pick), per-growth-stage water use, and **exceedance days** (days outside the crop's temperature limits).

**How it works**
- Reference evapotranspiration: FAO-56 Penman-Monteith on NASA POWER daily climatology (2016-2025), with two documented corrections: a **site-elevation correction** (lapse rate from the NASA grid-cell elevation to the site's Copernicus-DEM elevation) and the **FAO-56 Rev.1 humidity conditioning** for dry-site data (Eq. 2.6, set by each location's UNEP aridity index).
- Crop coefficients and heat-unit (GDD) phenology: FAO-56 Rev.1 (2025) tables and Paredes et al. (2025).
- Temperature tolerances and the planting-date selection method: Elnesr & Alazba (2016, King Saud University), adapted to minimise water per day.
- Autumn pick (sowing Jul 15-Dec 31): least water per day, shock-free dates first. Spring pick (Jan 1-Jul 14): least temperature stress among spring dates. For crops with an AquaCrop file the spring option also states what it costs in water productivity.

**Crops**

| Group | Crops | Status |
|---|---|---|
| Checked against the AquaCrop crop model | Tomato, Potato, Corn | Date rule within 5% of AquaCrop's best date in all 33 city x crop combinations |
| Not checkable against AquaCrop (no crop file) | Bell pepper, Onion, Carrot, Garlic, Lettuce, Sweet corn | Cards say "Not checked against AquaCrop" |
| Lower confidence (heat units are min/max ranges derived from 1998 durations) | Cucumber, Eggplant, Squash, Pumpkin, Green bean | Headline = the season pick with fewest exceedance days; cards say "Lower confidence" |
| Perennials | Grape, Apple | Perennial water cycle (no planting-date scan) |

Strawberry has no sourced stage heat units and is excluded from the planting-date scan. Not added: watermelon, radish, okra, molokhia (no heat-unit data in FAO-56 Rev.1); broccoli, melon, cabbage, cauliflower, spinach, lentil (failed the season-length checks).

**Cities covered:** Riyadh, Jeddah, Dammam, Najran, Jazan, Abha, Tabuk, Qassim, Madinah, Makkah, Hail

**What the dates mean:** the lowest-water feasible window under a published selection method, with heat and cold exposure shown. It is **not** a yield-optimised recommendation or an irrigation schedule.

### Feature 3 — Smart Plant Care Tracker
Tracks a saved plant through its growth cycle using GDD accumulation on the same corrected NASA POWER climatological baseline as Feature 2. Integrates Open-Meteo 5-day forecasts, computes a live daily water requirement via full FAO-56 Penman-Monteith (actual forecast solar radiation, temperature, humidity and wind, with the same humidity conditioning as the baseline) and compares it against the climatological baseline for the same days, isolating whether this week is running above or below the seasonal norm for that growth stage. Fires sourced temperature-tolerance alerts when forecast conditions exceed Elnesr & Alazba (2016) thresholds. Litres per plant are shown only when the user enters a planting density (plants per m²); otherwise the tracker shows mm/day (1 mm = 1 L per m²).

---

## How accurate is it?

### Feature 1

| Check | Result |
|---|---|
| Frozen benchmark (`feature1_eval/`) | 1,267 photos, 24/35 classes; v6p2 67.0% (95% CI 64.6-69.7%) guessing the crop, 76.5% (74.3-78.9%) given the crop |
| Contamination check | 83 of 1,267 benchmark photos (6.6%) have a near-duplicate in v1's own training data; accuracy on the remaining clean photos is 65.3% / 75.2% |
| 11 classes (e.g. apple frog-eye, grape esca, 4 strawberry conditions, tomato spider mites/target spot) | no real-field test photos exist in PlantDoc or PlantWild; accuracy on these is unknown |
| v6p2 vs v8p2 (EfficientNet-B0) | not significantly different on either real-world set (95% CI on the difference includes 0); v6p2 kept for being lighter |

**Known limitations**
- 11 of 35 classes have no real-world accuracy figure at all (see above).
- About 7% of the benchmark's official test photos were dropped for a label conflict (the same or a near-identical photo carries two different labels across datasets) — mostly in exactly the classes the model confuses (potato/tomato early blight, corn gray leaf spot/northern leaf blight), so the reported accuracy is mildly optimistic.
- The crop selector relies on the user naming the crop correctly; there is no independent crop detector.
- Rejection thresholds (confidence ≥ 0.70, normalised entropy ≤ 0.40) are fixed values, not calibrated against a validation set.

### Feature 2

| Check | Result |
|---|---|
| AquaCrop reference (tomato, corn, potato x 11 cities) | Water-per-day rule within 5% of AquaCrop's best water productivity in 31/33 combinations (against all viable dates; 33/33 within its own candidate pool); start date within 20 days of AquaCrop's best in 33/33 (same pool) |
| WMO 1991-2020 normals (5 stations) | Abha temperature error 6.3 C -> 0.8 C after the elevation correction |
| FAO-56 Rev.1 constants | 23 Kc triples, 32 heat-unit rows and 19 temperature thresholds checked against the PDF |
| Reference ET0 | Humidity correction lowers ET0 by 6-14% (about 12% typical); remaining uncertainty about +-15% (our estimate) |
| Saudi sowing calendars (Alsadon 2002, Table 5) | AquaCrop and the directorate calendars disagree on timing (calendars list spring dates AquaCrop disfavours); the advisor therefore shows both seasons. See `DEFENSE_PREP.md`, Part II |

**Known limitations**
- Absolute water amounts (mm, m³/ha) are estimates, uncertain by roughly 15%; wind speed is not independently verified.
- The 10 crops added after the first four are not checked against a crop model (none exists in AquaCrop for them); five of them use wide heat-unit ranges and are labelled lower confidence.
- Spring-planting water totals are less certain than autumn ones (simulated spring seasons run shorter than FAO's autumn-based durations).
- NASA's coastal day-night range is not corrected (tested at one station, Wejh); the warm-side elevation shifts (Makkah, Madinah) were not tested against a station.
- No yield, price, labour, soil or irrigation-efficiency model.

---

## Repository Structure

```
training/           CNN training pipeline
  train_cnn.py        main training script
  finetune_combined.py  PlantDoc + PlantWild fine-tuning
  predict.py          inference with OOD rejection
  model_loader.py     architecture-aware checkpoint loader
  evaluate_plantdoc.py  real-world evaluation (PlantDoc)
  evaluate_plantwild.py real-world evaluation (PlantWild)
  gradcam.py          Grad-CAM explainability
  config.py           central configuration

heatmap/            crop advisor pipeline
  advisor.py          main entry point
  season_simulator.py GDD phenology + ETc simulation
  season_picks.py     autumn + spring picks, lower-confidence headline rule, AquaCrop spring-cost table
  crop_database.py    per-crop parameters (FAO-56 Rev.1, Paredes 2025, Elnesr 2016)
  evapotranspiration.py  FAO-56 Penman-Monteith, Hargreaves, wind adjustment
  nasa_power.py       NASA POWER API integration + caching + elevation/humidity corrections
  site_elevation.py   site elevation (Copernicus DEM via Open-Meteo) + lapse-rate correction
  aridity.py          FAO-56 Rev.1 Eq. 2.6 humidity conditioning (UNEP aridity index)

care/               plant care tracker
  tracker.py          main entry point (GDD stage tracking + Open-Meteo live comparison + tolerance alerts)
  care_profiles.py    static disease/care knowledge base

api/main.py         FastAPI backend wrapping the three features
index.html          single-page web UI (Scan / Plan / Track)

research/           validation and sensitivity scripts (see research/README.md)
  patches/            the scripted, exact-match edits applied during the 1 Oct 2026 overhaul (audit trail)

models/cnn/         saved model checkpoints (gitignored except evaluation outputs)
  evaluation_report.txt  per-class F1 on PlantVillage test set
  plantdoc_evaluation.json  real-world accuracy (PlantDoc)
  plantwild_evaluation.json real-world accuracy (PlantWild)
  gradcam_outputs/    Grad-CAM visualizations

data/               datasets (gitignored)
  raw/                original downloaded datasets
  processed_v2/       train/val/test split (35 classes, 52,437 images)
  sources/            reference papers (Elnesr & Alazba 2016)
```

---

## Dataset

**Base training set (52,437 images, 35 classes):**
- PlantVillage (lab photos) — all 7 crops
- fgvc8 / Plant Pathology 2021 (real orchard photos) — Apple
- cds (real field photos) — Corn
- sms / Afzaal et al. 2022 (strawberry field photos) — Strawberry (new crop)

**Fine-tuning sets (real-world generalization):**
- PlantDoc — Singh et al. (2020), CODS-COMAD
- PlantWild v1 — Wei et al. (2024), 18,542 crowdsourced images

---

## Model Evolution

| Model | PlantVillage | PlantDoc | PlantWild | Notes |
|---|---|---|---|---|
| v1 | 93.57% | — | — | 27-class, PlantVillage only |
| v2 | 90.29% | 12.97% | — | 35-class, hybrid dataset |
| v3 | 94.17% | 55.68% | — | PlantDoc fine-tune |
| v4p2 | 96.07% | 65.41% | 62.23% | 224px, PD+PW fine-tune |
| v5p2 | 95.48% | 70.27% | 63.53% | 320px resolution |
| **v6p2** | **95.44%** | **70.81%** | **63.79%** | **384px — production model** |
| v7p2 | 95.00% | 70.81% | 62.32% | +tomato data — regression |
| v8p2 | 96.53% | 67.03% | 62.66% | EfficientNet-B0; not significantly different from v6p2 on either real-world set (see "How accurate is it?") |

The PlantDoc/PlantWild percentages above are each model's RAW score on the full test sets, kept for comparing models the same way they always were. They are not directly comparable to the de-duplicated, class-filtered 67.0%/76.5% in "How accurate is it?", which is the number to defend.

---

## Setup

```bash
git clone https://github.com/Moe-noob/Sgreenintel-ML.git
cd Sgreenintel-ML
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

No API keys required. NASA POWER and Open-Meteo (forecast and site-elevation data) are free, public services with no authentication.

**Data:** raw datasets are not committed (large files). The processed split in `data/processed_v2/` must be generated locally using `training/prepare_data_v2.py` after downloading the raw sources.

---

## Running

```bash
# Start the API (docs at http://localhost:8000/docs), then open index.html in a browser
uvicorn api.main:app --reload --port 8000

# Predict disease from a leaf photo
python training\predict.py path\to\leaf.jpg

# Run the crop advisor for a city
python -c "from heatmap.advisor import get_recommendations, print_recommendations; print_recommendations(get_recommendations('riyadh'))"

# Check plant care status (add plants_per_m2=2.5 to get_plant_status for litres per plant)
python -c "
from care.tracker import get_plant_status, print_plant_status
print_plant_status(get_plant_status('Tomato', 'riyadh', '2026-09-01'))
"

# Predict disease, telling the model the crop (narrows the 35 classes to that crop's own; ~10 points more accurate)
python -c "
from training.predict_api import predict_structured
import json; print(json.dumps(predict_structured('path/to/leaf.jpg', crop='Tomato'), indent=2))
"

# Re-run the Feature 1 benchmark (see feature1_eval/README.md for the full sequence)
python -m feature1_eval.evaluate --legacy models\cnn\mobilenetv2_sgreenintel_v6p2.pth --split test --final --purpose "..."
python -m feature1_eval.contamination --predictions feature1_eval\work\eval_mobilenetv2_sgreenintel_v6p2\test\predictions.csv

# Verify the humidity correction behaves as documented (needs the NASA cache)
python research\check_aridity_correction.py

# Re-run the AquaCrop reference check (pip install aquacrop first; takes about 10 minutes)
python research\aquacrop_reference_check.py --summary

# Evaluate on PlantDoc / PlantWild real-world test sets
python training\evaluate_plantdoc.py
python training\evaluate_plantwild.py
```

---

## Key References

- Allen et al. (1998). FAO Irrigation and Drainage Paper No. 56. FAO, Rome.
- Pereira, Allen, Paredes, López-Urrea, Raes, Smith, Kilic & Salman (2025). *Crop evapotranspiration — Guidelines for computing crop water requirements* (FAO56 Rev.1). FAO Irrigation and Drainage Paper 56 Rev.1, doi:10.4060/cd6621en. (Updated Kc, GDD stage tables, and the humidity conditioning used for dry-site weather data, Sec. 2.5.)
- Paredes et al. (2025). Growing-degree-day stage durations for FAO56rev. *Agricultural Water Management* 319:109758.
- Elnesr & Alazba (2016). A Spreadsheet Model to Select Vegetables Planting Dates. *Computers and Electronics in Agriculture*, King Saud University.
- Alsadon (2002). Compatibility between dates planned based on heat units and dates suggested from regional offices of the Ministry of Agriculture (Saudi Arabia). (Table 5 of directorate sowing dates is used as a benchmark.)
- Steduto, Hsiao, Raes & Fereres (2012) and Raes et al. (2023). AquaCrop, the FAO crop model used as the independent check.
- Copernicus 90 m DEM (via Open-Meteo elevation API) and WMO 1991-2020 climate normals (station checks of the elevation correction).
- Singh et al. (2020). PlantDoc: A Dataset for Visual Plant Disease Detection. CODS-COMAD 2020.
- Wei et al. (2024). PlantWild: A Benchmark for In-the-Wild Plant Disease Recognition. arXiv 2408.03120.
- Afzaal et al. (2022). Strawberry disease segmentation dataset (sms). *Sensors*, MDPI.