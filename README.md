# SGreen Intel — ML Core

AI-powered agricultural platform for Saudi farmers. Three features: CNN plant disease detection, location-based crop advisor, and smart plant care tracker. Built as a Najran University CS capstone aligned with Saudi Arabia's Vision 2030 Green Initiative.

---

## Features

### Feature 1 — CNN Plant Disease Detection
MobileNetV2-based classifier for 35 disease/healthy classes across 7 crops. Trained on a hybrid lab+field dataset and fine-tuned progressively on real-world photo collections to reduce domain gap.

**Crops covered:** Tomato, Potato, Bell Pepper, Grape, Apple, Corn, Strawberry

**Final model (v6p2):**
- PlantVillage test set: **95.44%** accuracy
- PlantDoc real-world test: **70.81%** accuracy
- PlantWild real-world test: **63.79%** accuracy
- Domain gap reduced from 77pp (lab-only baseline) to 23pp through targeted fine-tuning

### Feature 2 — Location-Based Crop Advisor
Planting-date simulation for 11 Saudi cities using FAO-56 Penman-Monteith evapotranspiration, GDD-based phenology, and the Elnesr & Alazba (2016, KSU) planting-date selection methodology. Outputs per-growth-stage water requirements and temperature-tolerance alerts.

**Cities covered:** Riyadh, Jeddah, Dammam, Najran, Jazan, Abha, Tabuk, Qassim, Madinah, Makkah, Hail

### Feature 3 — Smart Plant Care Tracker
Tracks a saved plant through its growth cycle using GDD accumulation on the same NASA POWER climatological baseline as Feature 2. Integrates OpenWeatherMap 5-day forecasts and fires sourced temperature-tolerance alerts when forecast conditions exceed Elnesr & Alazba (2016) thresholds.

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
  crop_database.py    per-crop parameters (FAO-56, Elnesr 2016)
  nasa_power.py       NASA POWER API integration + caching

care/               plant care tracker
  tracker.py          main entry point (GDD stage tracking + OWM alerts)
  care_profiles.py    static disease/care knowledge base

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
| v8p2 | 96.53% | 67.03% | 62.66% | EfficientNet-B0 — better lab, worse real-world |

---

## Setup

```bash
git clone https://github.com/Moe-noob/Sgreenintel-ML.git
cd Sgreenintel-ML
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Required environment variables (.env, not committed):**
```
OWM_API_KEY=your_openweathermap_api_key
```

**Data:** raw datasets are not committed (large files). The processed split in `data/processed_v2/` must be generated locally using `training/prepare_data_v2.py` after downloading the raw sources.

---

## Running

```bash
# Predict disease from a leaf photo
python training\predict.py path\to\leaf.jpg

# Run the crop advisor for a city
python -c "from heatmap.advisor import get_recommendations, print_recommendations; print_recommendations(get_recommendations('riyadh'))"

# Check plant care status
python -c "
from care.tracker import get_plant_status, print_plant_status
print_plant_status(get_plant_status('Tomato', 'riyadh', '2026-09-01'))
"

# Evaluate on PlantDoc real-world test set
python training\evaluate_plantdoc.py

# Evaluate on PlantWild real-world test set
python training\evaluate_plantwild.py
```

---

## Key References

- Allen et al. (1998). FAO Irrigation and Drainage Paper No. 56. FAO, Rome.
- Elnesr & Alazba (2016). A Spreadsheet Model to Select Vegetables Planting Dates. *Computers and Electronics in Agriculture*, King Saud University.
- Singh et al. (2020). PlantDoc: A Dataset for Visual Plant Disease Detection. CODS-COMAD 2020.
- Wei et al. (2024). PlantWild: A Benchmark for In-the-Wild Plant Disease Recognition. arXiv 2408.03120.
- Paredes et al. (2025). FAO56rev — Updated crop coefficients and GDD phenology.
- Afzaal et al. (2022). Strawberry disease segmentation dataset (sms). *Sensors*, MDPI.