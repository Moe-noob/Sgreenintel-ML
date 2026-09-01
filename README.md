# SGreen Intel — ML Core

ML components for SGreen Intel: CNN plant disease detection and KSA geospatial suitability heatmap.

## Structure
- `data/` — PlantVillage (raw + processed), gitignored
- `training/` — CNN training pipeline
- `heatmap/` — NASA POWER integration, suitability model, grid precomputation
- `models/` — saved model artifacts, gitignored
- `api/` — Flask service exposing prediction/heatmap endpoints for the frontend/backend
- `notebooks/` — exploratory work

## Crops covered (CNN)
Tomato, Potato, Bell Pepper, Grape, Apple, Corn

## Setup
See `requirements.txt`. Details TBD as pipeline is built out.