"""
Central settings for the Feature 1 evaluation kit. Paths can be overridden with environment
variables so the same code runs locally, on Colab and on a lab GPU:

    F1E_DATA_ROOT   folder that holds the downloaded datasets (see RUNBOOK.md)
    F1E_WORK_DIR    where manifests, splits, checkpoints and reports are written
    F1E_BENCHMARK_DIR  where the frozen benchmark and its usage log live
                     (on Colab: a Google Drive folder, so the freeze survives a disconnect)
"""

import os
from pathlib import Path

PKG = Path(__file__).resolve().parent
REPO = PKG.parent

DATA_ROOT = Path(os.environ.get("F1E_DATA_ROOT", REPO / "data" / "raw"))
WORK_DIR = Path(os.environ.get("F1E_WORK_DIR", PKG / "work"))
SOURCES_FILE = PKG / "sources.json"
BENCHMARK_DIR = Path(os.environ.get("F1E_BENCHMARK_DIR", PKG / "benchmark"))   # frozen benchmark (small text files, committed)

# ---- class inclusion (plan, Step 2) ----
MIN_FIELD_TRAIN = 150    # real-field training images a class needs to enter the model
MIN_FIELD_TEST = 30      # held-out real-field test images a class needs

# ---- splitting ----
FIELD_TEST_FRACTION = 0.20   # for field sources WITHOUT an official test split
FIELD_VAL_FRACTION = 0.10    # carved from field training pools (by duplicate group)
SPLIT_SALT = "sgreen-f1v2"   # changing this changes every hash-based split: don't

# ---- de-duplication ----
PHASH_MAX_DISTANCE = 6       # Hamming distance (of 64 bits) treated as a near-duplicate

# ---- training defaults (overridable on the command line) ----
IMAGE_SIZE = 224
SEED = 42
