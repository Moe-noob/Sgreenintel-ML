# Feature 1 v2: runbook (Google Colab or any CUDA GPU)

> **New to this? Use [`colab/GUIDE.md`](colab/GUIDE.md) and the click-through notebook `colab/train_feature1_v2.ipynb`.** They run exactly these steps, check each result and survive Colab disconnects. This page is the same procedure as plain commands.
>
> Two settings matter on Colab:
> - `F1V2_BENCHMARK_DIR` puts the frozen benchmark on Google Drive, so the freeze survives a disconnect.
> - `train.py --resume` continues a run from its `last.pt` after a disconnect.

These are the steps that turn the code in `feature1_v2/` into a trained, calibrated and evaluated model. The code was built and tested on CPU with synthetic images (`python -m unittest discover -s feature1_v2/tests -t .`, 37 tests). **No real training has been run yet**: the build environment had no GPU and no access to the datasets. So every accuracy number for v2 comes from running this runbook.

Order matters. Steps 1–4 build and **freeze** the benchmark before any model is trained, so nothing can be tuned on it.

| Step | What | Colab T4 time (rough) |
|---|---|---|
| 0 | setup | 5 min |
| 1 | download data | 20–40 min |
| 2–4 | manifest, de-duplication, frozen splits | 15–30 min |
| 5 | v1 baseline on the field validation set | 5 min |
| 6 | backbone comparison (decision gate 1) | 1–2 h per fine-tune |
| 7 | calibration | 5 min |
| 8 | leaf detector (decision gate 2) | 1–2 h |
| 9 | serve | – |
| 10 | final benchmark run (once) | 10 min |

A bigger GPU (A100 / L4) only makes step 6 faster. Raise `--batch` and keep the learning rate rule (`lr` scales with `batch/32` by default).

---

## 0. Setup

```bash
# Colab: Runtime -> Change runtime type -> GPU
from google.colab import drive; drive.mount('/content/drive')

git clone -b claude/compassionate-hopper-lh08ol https://github.com/moe-noob/Sgreenintel-ML.git
cd Sgreenintel-ML
pip install -r feature1_v2/requirements.txt

# keep data and results on Drive so a disconnect loses nothing
export F1V2_DATA_ROOT=/content/drive/MyDrive/sgreen/data/raw
export F1V2_WORK_DIR=/content/drive/MyDrive/sgreen/f1v2_work
export F1V2_BENCHMARK_DIR=/content/drive/MyDrive/sgreen/f1v2_benchmark   # the frozen benchmark must survive disconnects
```

(In a Colab cell, use `%env F1V2_DATA_ROOT=...` instead of `export`.)

## 1. Data

Use the same layout v1 used, under `$F1V2_DATA_ROOT`:

| Folder under `F1V2_DATA_ROOT` | Source | How |
|---|---|---|
| `plantwild/plantwild/images/<class>/…` and `plantwild/plantwild/trainval.txt` | PlantWild v1, 89 classes (Wei et al. 2024) | download link in github.com/tqwei05/MVPDR (same files as v1 used) |
| `PlantDoc-Dataset/train`, `PlantDoc-Dataset/test` | PlantDoc (Singh et al. 2020), CC BY 4.0 | `git clone https://github.com/pratikkayal/PlantDoc-Dataset` |
| `../processed_v2/{train,val,test}` (= `data/processed_v2`) | v1's PlantVillage + fgvc8 + cds + sms | `python training/prepare_data_v2.py` (v1 script) or copy from v1's machine |
| `PlantDoc-Object-Detection-Dataset` | PlantDoc boxes, for the leaf detector only | `git clone https://github.com/pratikkayal/PlantDoc-Object-Detection-Dataset` |

**Optional sources** (disabled templates in `feature1_v2/sources.json`). Each one adds crops or cases:
- `cucumber_extra`: cucumber field dataset (PMC10338290).
- `eggplant_field`: Mendeley `pwvpb658rm`.
- `okra_onion_melon_extra`: any real-field okra, onion or melon set you find.
- `non_plant`: e.g. about 2,000 COCO val2017 images. This trains and tests the "not a supported leaf" answer.

To enable one:
1. Download it and put it in the folder named by `path`.
2. Run `python -m feature1_v2.data.manifest --list-labels <name>` to print its folder names.
3. Fill `label_map` (raw folder name → `crop__condition` from `feature1_v2/taxonomy.py`, or `_unsupported`).
4. Set `"enabled": true`.

Add every source **before** step 4. Adding one later changes the benchmark, which needs a deliberate `--force-refreeze` (see step 4).

## 2. Manifest

```bash
python -m feature1_v2.data.manifest
```

Writes `$F1V2_WORK_DIR/manifest.csv` and prints images per source and label. Raw labels with no mapping are listed. Fix them in `taxonomy.py` or the source's `label_map`, or accept that they are skipped.

## 3. Near-duplicate detection

```bash
python -m feature1_v2.data.dedupe          # perceptual hash, Hamming distance <= 6
```

Writes `hashes.csv` and `dup_groups.json`. PlantDoc and PlantWild were both collected by web image search, so the same photo can be in both, or in both train and test.

## 4. Splits and the frozen benchmark

```bash
python -m feature1_v2.data.splits
```

- Applies the class inclusion rule: at least 150 field training photos and 30 held-out photos. Excluded classes are printed.
- Removes leakage and label conflicts between duplicate groups.
- Writes `splits.csv`, `classes.json` and `split_report.json`.
- **Freezes** `feature1_v2/benchmark/` (`benchmark.csv` plus SHA-256).

**Commit** `feature1_v2/benchmark/benchmark.csv`, `FROZEN.json` (SHA-256 of the image list, per-class counts) and `work/split_report.json` (copy it next to the benchmark) to the repo. From now on:
- `load_split("test")` refuses to run without `--final`, and every final use is logged in `benchmark/usage_log.txt`.
- Re-running splits with different data stops with an error unless you pass `--force-refreeze`. Only do that if you accept that all earlier benchmark numbers are no longer comparable.

## 5. Baseline: v1 (v6p2) on the same field validation photos

```bash
python -m feature1_v2.evaluate --legacy models/cnn/mobilenetv2_sgreenintel_v6p2.pth --split val
```

Use the actual v1 checkpoint path. It is not in git (`*.pth` is ignored), so copy it from where v1 was trained. The report includes:
- accuracy and macro-F1 with 95 % confidence intervals;
- the "crop given" mode;
- `share_unknown_to_model`: the share of photos whose class v1 cannot output at all.

This number replaces the stale JSONs in `models/cnn/`.

## 6. Train and compare backbones (decision gate 1)

Start with linear probes (fast), then fine-tune the two best:

```bash
python -m feature1_v2.train --backbone dinov2_s    --mode linear   --epochs 10 --out $F1V2_WORK_DIR/runs/dinov2_s_lin
python -m feature1_v2.train --backbone siglip_b    --mode linear   --epochs 10 --out $F1V2_WORK_DIR/runs/siglip_b_lin
python -m feature1_v2.train --backbone convnextv2_t --mode finetune --epochs 25 --out $F1V2_WORK_DIR/runs/convnextv2_t_ft
python -m feature1_v2.train --backbone dinov2_s    --mode finetune --epochs 25 --out $F1V2_WORK_DIR/runs/dinov2_s_ft
python -m feature1_v2.train --backbone effv2_s     --mode finetune --epochs 25 --out $F1V2_WORK_DIR/runs/effv2_s_ft
# bigger GPU: dinov2_b, --img-size 336 (resolution is an ablation, keep it only if val improves)
```

Then evaluate each run and compare it with v1 on the same photos:

```bash
python -m feature1_v2.evaluate --ckpt $F1V2_WORK_DIR/runs/dinov2_s_ft/best.pt --split val
python -m feature1_v2.compare $F1V2_WORK_DIR/v1_baseline/eval_val/predictions.csv \
                              $F1V2_WORK_DIR/runs/dinov2_s_ft/eval_val/predictions.csv
```

**Gate:** continue only with a model whose paired-bootstrap interval vs v1 is entirely above 0 (`compare` prints "B better").

**Ablations** for the report: one flag at a time on the best backbone, each judged by the same paired comparison.

| Flag | Values | What it switches |
|---|---|---|
| `--background-swap` | 0 / 0.5 | background replacement on lab photos |
| `--cutmix` | 0 / 0.3 | CutMix |
| `--field-weight` | 1 / 3 | how much field photos are oversampled |
| `--ema` | 0 / 0.9998 | EMA weights |

## 7. Calibration (field validation split)

```bash
python -m feature1_v2.calibrate --ckpt $F1V2_WORK_DIR/runs/BEST/best.pt --target 0.90 --tta
python -m feature1_v2.evaluate  --ckpt $F1V2_WORK_DIR/runs/BEST/best.pt --split val --tta
```

`calibration.json` (next to `best.pt`) holds:
- the temperature;
- the confidence thresholds that give 90 % accuracy on accepted photos (auto mode and crop-given mode);
- the energy threshold for "not a supported leaf".

`--target` sets the trade-off: higher means fewer but more reliable answers.

Optional: if you need a small model, distil into MobileNetV3 and treat the result like any other checkpoint (calibrate, evaluate, compare):

```bash
python -m feature1_v2.distill --teacher $F1V2_WORK_DIR/runs/BEST/best.pt --student mnv3_l --out $F1V2_WORK_DIR/runs/mnv3_kd
```

## 8. Leaf detector (decision gate 2)

```bash
python -m feature1_v2.detector.prepare_plantdoc --src $F1V2_DATA_ROOT/PlantDoc-Object-Detection-Dataset \
       --out $F1V2_WORK_DIR/detector/yolo        # benchmark images are excluded from detector training
yolo detect train data=$F1V2_WORK_DIR/detector/yolo/leaf.yaml model=yolov8n.pt imgsz=640 epochs=80 \
       project=$F1V2_WORK_DIR/detector/runs name=leaf
python -m feature1_v2.detector.evaluate_gain --ckpt $F1V2_WORK_DIR/runs/BEST/best.pt \
       --detector $F1V2_WORK_DIR/detector/runs/leaf/weights/best.pt
```

**Gate:** keep the detector only if `detector_gain.json` says "keep detector" (95 % interval of the accuracy gain above 0).

## 9. Serve

Add the router to `api/main.py`, two lines like Feature 2 v2:

```python
sys.path.insert(0, str(PROJECT_ROOT))
from feature1_v2.api_router import router as f1v2_router; app.include_router(f1v2_router)
```

```bash
export F1V2_CKPT=.../runs/BEST/best.pt          # calibration.json must be next to it
export F1V2_DETECTOR=.../leaf/weights/best.pt    # only if gate 2 passed
uvicorn api.main:app --port 8000
```

Then open `feature1_v2/demo.html` in a browser. Smoke test from the command line:

```bash
curl -F files=@leaf1.jpg -F files=@leaf2.jpg -F crop=tomato -F lang=ar -F city=riyadh localhost:8000/v2/disease/predict
```

## 10. Final benchmark run (once, at the end)

```bash
python -m feature1_v2.evaluate --legacy models/cnn/mobilenetv2_sgreenintel_v6p2.pth --split test --final --purpose "final: v1 baseline"
python -m feature1_v2.evaluate --ckpt $F1V2_WORK_DIR/runs/BEST/best.pt --split test --final --tta --purpose "final: v2 BEST"
python -m feature1_v2.compare $F1V2_WORK_DIR/v1_baseline/eval_test/predictions.csv $F1V2_WORK_DIR/runs/BEST/eval_test/predictions.csv
```

Paste the `report.md` tables and the `compare` line into `DOCUMENTATION.md` section 7, and commit `benchmark/usage_log.txt`. If you change the model after this, the next benchmark run must be reported as a second use, not hidden.
