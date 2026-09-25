# Legacy: Grid-Based Suitability Approach (superseded)

This folder holds the **original** implementation of Feature 2 (crop/location
suitability), from before the project pivoted to the current planting-date
simulation in `heatmap/advisor.py`.

## What this was

A geospatial grid approach: Saudi Arabia was divided into a coordinate grid
(`data/processed/saudi_grid.json`, built from the GeoJSON region boundaries in
`data/geo/`), and `build_grid.py` + `precompute.py` computed a rough crop
suitability score for each grid cell using NASA POWER climate data and simple
temperature-range matching. `visualize.py` / `visualize_v2.py` rendered these
as a heatmap; `debug_border.py` and `inspect_geo.py`/`inspect_results.py` were
used to debug the border/grid geometry during development.

## Why it was replaced

The suitability score used unsourced, hand-picked weights to combine
temperature fit and rough water estimates into a single number -- there was
no principled way to defend where those weights came from. The project
pivoted to the current approach in `heatmap/advisor.py`: a planting-date
simulation using FAO-56 Penman-Monteith ET0, GDD-based crop phenology, and
the Elnesr & Alazba (2016, KSU) planting-date selection methodology --
every number in the current system traces back to a cited source.

## Status

Not used by the API, the frontend, or any current feature. Kept for
reference and to show the project's methodology evolution -- not
maintained, not guaranteed to run against the current `nasa_power.py`
interface (which changed significantly during the pivot).
