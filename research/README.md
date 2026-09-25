# Research / Methodology Validation Scripts

Standalone scripts that tested a specific methodological question and
produced a documented finding, referenced in the project report. None of
these are called by the production API, frontend, or training pipeline --
they're one-off validation work, kept visible rather than deleted since
they're evidence for specific claims made in the report.

## compare_climatology_methods.py

Tests whether an alternative smoothing method (harmonic/Fourier regression,
Gaussian-weighted smoothing, LOESS) would improve on the moving-average
climatology used in `heatmap/nasa_power.py`, via leave-one-year-out
cross-validation across all 11 known cities.

**Finding:** none of the three alternatives offer a practically meaningful
improvement (best case ~0.003-0.007 degC MAE difference). The existing
moving-average method is kept as production. Full detail in the commit
history (search for "climatology methodology validation").

Does not modify `nasa_power.py` -- only imports its read-only functions.
Run: `python research/compare_climatology_methods.py`

## sanity_check.py

Quick verification that `training/dataset.py`'s data loading, class list,
and class-weight computation produce the expected shapes and values
(37,526 train / 8,029 val / 8,074 test images, 35 classes). Used during
initial CNN dataset setup and re-run occasionally to confirm the pipeline
still loads correctly after dataset changes.

Run: `python research/sanity_check.py` (requires `data/processed_v2/` to
exist locally -- see the main README's setup section).
