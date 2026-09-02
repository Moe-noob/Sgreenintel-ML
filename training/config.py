"""
Central configuration for SGreen Intel CNN training.
Change values here rather than hardcoding them elsewhere in the pipeline.
"""

import torch
from pathlib import Path

# ---- Paths ----
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
TRAIN_DIR = DATA_DIR / "train"
VAL_DIR = DATA_DIR / "val"
TEST_DIR = DATA_DIR / "test"
MODEL_SAVE_DIR = PROJECT_ROOT / "models" / "cnn"

# ---- Data ----
IMAGE_SIZE = 224          # required input size for MobileNetV2
BATCH_SIZE = 16           # kept modest deliberately for GTX 1650 (4GB VRAM)
NUM_WORKERS = 2           # kept low to avoid Windows dataloader stalls
SEED = 42

# ---- Model ----
NUM_CLASSES = 27          # 6 crops, 27 crop-disease/healthy classes (see README)

# ---- Training ----
EPOCHS = 15                # starting point — adjust after first run based on val curves
LEARNING_RATE = 0.001
WEIGHT_DECAY = 1e-4
USE_CLASS_WEIGHTS = True   # addresses imbalance, e.g. Tomato Mosaic Virus (261) vs Yellow Leaf Curl Virus (3749)

# ---- Device ----
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ---- Checkpointing ----
CHECKPOINT_NAME = "mobilenetv2_sgreenintel.pth"
BEST_MODEL_PATH = MODEL_SAVE_DIR / CHECKPOINT_NAME