"""
Writes train_feature1_v2.ipynb from the cells below (so the notebook can be
reviewed and edited as plain Python). Re-run after editing:

    python -m feature1_v2.colab.build_notebook
"""

from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).resolve().parent
CELLS = []


def md(text):
    CELLS.append(nbf.v4.new_markdown_cell(text.strip()))


def code(text):
    CELLS.append(nbf.v4.new_code_cell(text.strip()))


md("""
# 🌿 Feature 1 v2: train the new plant-disease model

**How to use this notebook:** press ▶ (the play button on the left of each grey code box), one box at a time, **from top to bottom**. Wait until the box finishes before you press the next one (the spinning circle stops).

- ✅ means the step worked: go to the next box.
- ❌ means something needs fixing: the message says what to do.
- If Colab disconnects (it will on the free plan), read **"Colab disconnected?"** in `GUIDE.md`, Part D. Nothing is lost: everything important is saved in your Google Drive.

The full beginner guide is `feature1_v2/colab/GUIDE.md`.
""")

md("""
## 0. Settings
You normally don't change anything here.
""")
code(r'''
import os
DRIVE_FOLDER = "/content/drive/MyDrive/sgreen"     # the folder you made in Google Drive (GUIDE.md, Part A)
DRY_RUN = os.environ.get("F1V2_DRY_RUN") == "1"     # developer self-check with fake data. Leave as it is.
if DRY_RUN:
    DRIVE_FOLDER = os.environ["F1V2_DRY_DRIVE"]
print("Settings loaded.", "(DRY RUN with fake data)" if DRY_RUN else "")
''')

md("""
## 1. Check the GPU  (10 seconds)
""")
code(r'''
import json, shutil, subprocess, sys, time, zipfile
from pathlib import Path

PY = sys.executable

def ok(msg):
    print("✅", msg)

def warn(msg):
    print("⚠️ ", msg)

class StopHere(Exception):
    pass

def fail(msg):
    raise StopHere("\n\n❌ " + msg + "\n")

def sh(cmd, env=None, check=True):
    """Run a command and show its output live."""
    print("▶", " ".join(str(c) for c in cmd))
    p = subprocess.Popen([str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         bufsize=1, env={**os.environ, **(env or {})})
    for line in p.stdout:
        print(line, end="")
    p.wait()
    if check and p.returncode != 0:
        fail("The step above stopped with an error. Scroll up a little, copy the last lines that mention "
             "'Error', and send them to Claude.")
    return p.returncode

import torch
if torch.cuda.is_available():
    ok(f"GPU found: {torch.cuda.get_device_name(0)}. Go to the next box.")
elif DRY_RUN:
    warn("No GPU, but this is a dry run with fake data, so that's fine.")
else:
    fail("No GPU. In the menu: Runtime → Change runtime type → choose 'T4 GPU' → Save. "
         "Then start again from the first box.")
''')

md("""
## 2. Connect your Google Drive  (30 seconds)
A window will ask you to allow access: choose your Google account and press **Allow / Continue**.
""")
code(r'''
if not DRY_RUN:
    from google.colab import drive
    drive.mount("/content/drive")
D = Path(DRIVE_FOLDER)
if not D.is_dir():
    fail(f"I can't find the folder {DRIVE_FOLDER}. In Google Drive, open 'My Drive', create a folder named "
         "exactly  sgreen  (small letters) and upload your 5 files into it (GUIDE.md, Part A).")
ok(f"Google Drive connected. Found the folder {D}")
''')

md("""
## 3. Unpack the code and the photos  (first time 10–20 min, after that ~5 min)
Copies everything from Drive to Colab's fast disk. Run this again after every disconnect.
""")
code(r'''
LOCAL = Path("/content") if not DRY_RUN else Path(os.environ["F1V2_DRY_LOCAL"])
NEEDED = {
    "code.zip": "the code: GitHub → branch claude/compassionate-hopper-lh08ol → green 'Code' button → Download ZIP",
    "plantwild.zip": "your folder data/raw/plantwild, zipped",
    "PlantDoc-Dataset.zip": "your folder data/raw/PlantDoc-Dataset, zipped",
    "processed_v2.zip": "your folder data/processed_v2, zipped",
    "mobilenetv2_sgreenintel_v6p2.pth": "the old model file from models/cnn/ (not zipped)",
}
missing = [f"   • {name}  ←  {what}" for name, what in NEEDED.items()
           if not (D / name).exists() or (D / name).stat().st_size == 0]
if missing:
    names = "\n".join(sorted(p.name for p in D.iterdir())) or "(the folder is empty)"
    fail("These files are missing (or empty) in your Drive folder 'sgreen':\n" + "\n".join(missing) +
         "\n\nThe names must match exactly. What I see in the folder right now:\n" + names)

def find_dir(root, test, depth=5):
    """First folder under root (breadth-first) for which test(folder) is true."""
    level = [Path(root)]
    for _ in range(depth):
        nxt = []
        for d in level:
            try:
                if test(d):
                    return d
                nxt += [c for c in sorted(d.iterdir()) if c.is_dir() and not c.name.startswith(("__MACOSX", "."))]
            except PermissionError:
                pass
        level = nxt
    return None

def unpack(zip_name, test, target, what):
    target = Path(target)
    if target.exists():
        ok(f"{what}: already unpacked")
        return target
    tmp = LOCAL / "unzipped" / zip_name[:-4]
    if not (tmp / ".done").exists():
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True)
        print(f"Unpacking {zip_name} ... (large files take several minutes)")
        if shutil.which("unzip"):
            sh(["unzip", "-q", "-o", D / zip_name, "-d", tmp])
        else:
            zipfile.ZipFile(D / zip_name).extractall(tmp)
        (tmp / ".done").touch()
    found = find_dir(tmp, test)
    if found is None:
        fail(f"{zip_name} does not contain what I expected ({what}). Did you zip the right folder? "
             "See GUIDE.md, Part A.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(found.resolve(), target_is_directory=True)
    ok(f"{what}: ready")
    return target

def has_leaf_folders(d):
    return (d / "train").is_dir() and (d / "test").is_dir() and any(c.name.lower().endswith("leaf") for c in (d / "train").iterdir())

CODE = unpack("code.zip", lambda d: (d / "feature1_v2" / "config.py").exists(), LOCAL / "code", "code")
RAW = LOCAL / "data" / "raw"
unpack("plantwild.zip", lambda d: (d / "trainval.txt").exists() and (d / "images").is_dir(),
       RAW / "plantwild" / "plantwild", "PlantWild photos")
unpack("PlantDoc-Dataset.zip", has_leaf_folders, RAW / "PlantDoc-Dataset", "PlantDoc photos")
unpack("processed_v2.zip",
       lambda d: all((d / s).is_dir() for s in ("train", "val", "test")) and any("___" in c.name for c in (d / "train").iterdir()),
       LOCAL / "data" / "processed_v2", "old training photos (processed_v2)")

WORK = D / "f1v2_work"            # results: saved on Drive, survive disconnects
BENCH = D / "f1v2_benchmark"      # the locked final-exam list: saved on Drive
WORK.mkdir(exist_ok=True)
V1 = D / "mobilenetv2_sgreenintel_v6p2.pth"
os.environ.update(F1V2_DATA_ROOT=str(RAW), F1V2_WORK_DIR=str(WORK), F1V2_BENCHMARK_DIR=str(BENCH))
os.chdir(CODE)
sys.path.insert(0, str(CODE))

def winner_dir():
    if not (WORK / "winner.txt").exists():
        fail("No winner chosen yet. Run box 9 first.")
    return WORK / "runs" / (WORK / "winner.txt").read_text().strip()

ok("Everything is unpacked. Go to the next box.")
''')

md("""
## 4. Install the extra software  (2–3 min)
""")
code(r'''
if not DRY_RUN:
    sh([PY, "-m", "pip", "install", "-q", "-r", "feature1_v2/requirements.txt"])
import timm
ok(f"Software ready (timm {timm.__version__}).")
''')

md("""
## 5. Self-test of the code  (about 1 min)
Runs the 37 automatic checks on fake images. They say nothing about accuracy, only that the code runs on this machine.
""")
code(r'''
import tempfile
sh([PY, "-m", "unittest", "discover", "-s", "feature1_v2/tests", "-t", "."],
   env={"F1V2_BENCHMARK_DIR": tempfile.mkdtemp(), "F1V2_WORK_DIR": tempfile.mkdtemp()})
ok("All checks passed. Go to the next box.")
''')

md("""
## 6. Prepare the photos and lock the final exam  (only once: 20–40 min)
This step:
- lists every photo;
- finds near-identical photos so the same picture is never in both training and test;
- splits the photos into **training** (the model learns from them), **validation** (we compare models on them) and the **final exam** (locked: used once, at the very end).

If it already ran in an earlier session, it skips itself.
""")
code(r'''
from collections import defaultdict
MIN_ARGS = ["--min-train", "10", "--min-test", "5"] if DRY_RUN else []
if (WORK / "splits.csv").exists() and (BENCH / "FROZEN.json").exists():
    ok("Already prepared in an earlier session: skipping.")
else:
    sh([PY, "-m", "feature1_v2.data.manifest"])
    sh([PY, "-m", "feature1_v2.data.dedupe"])
    sh([PY, "-m", "feature1_v2.data.splits"] + MIN_ARGS)

rep = json.loads((WORK / "split_report.json").read_text())
classes = json.loads((WORK / "classes.json").read_text())
by_crop = defaultdict(list)
for c in classes:
    by_crop[c.split("__")[0]].append(c)
print(f"\n{'crop / condition':42} {'train':>7} {'valid.':>7} {'exam':>6}")
for crop in sorted(by_crop):
    for c in by_crop[crop]:
        n = [rep["counts"][s].get(c, 0) for s in ("train", "val", "test")]
        print(f"{c:42} {n[0]:7} {n[1]:7} {n[2]:6}")
print(f"\nPhotos removed because the same picture appeared in training and test: {rep['dropped_leak_test'] + rep['dropped_leak_val']}")
print(f"Photos removed because copies had different labels: {rep['dropped_label_conflict']}")
if rep["excluded_classes"]:
    print("\nNot enough real photos (left out for now):")
    for c, n in rep["excluded_classes"].items():
        print(f"   {c:40} real training photos {n['field_train']}, exam photos {n['test']}")
frozen = json.loads((BENCH / "FROZEN.json").read_text())
ok(f"{len(classes)} classes ready. Final exam locked: {frozen['n_images']} photos (fingerprint {frozen['sha256'][:12]}).")
''')

md("""
## 7. Score of the OLD model  (5 min)
The old model (v6p2) is tested on the validation photos. This is the number the new model has to beat.
""")
code(r'''
v1_rep = WORK / "v1_baseline" / "eval_val" / "report.json"
if not v1_rep.exists():
    sh([PY, "-m", "feature1_v2.evaluate", "--legacy", V1, "--split", "val"])
r = json.loads(v1_rep.read_text())
print(f"\nOld model on real validation photos:  {r['auto']['accuracy']:.1%} correct "
      f"({r['crop_given']['accuracy']:.1%} when the crop is known)")
print(f"Photos of crops/diseases the old model can't recognise at all: {r['share_unknown_to_model']:.0%}")
ok("Baseline measured. Go to the next box.")
''')

md("""
## 8. Train the new models
Each box trains one model. Times are for the free T4 GPU.

**If Colab disconnects in the middle:** reconnect, run boxes 0–4 again, then press ▶ on the same training box. It **continues where it stopped**; it does not start over.

You will see one line per epoch (one round of learning), like `{"epoch": 3, ... "val_accuracy": 0.71 ...}`. `val_accuracy` should mostly go up.
""")
code(r'''
RUNS = {   # name: (model, mode, epochs)
    "dinov2_s_lin":    ("dinov2_s", "linear", 10),
    "dinov2_s_ft":     ("dinov2_s", "finetune", 25),
    "convnextv2_t_ft": ("convnextv2_t", "finetune", 25),
    "siglip_b_lin":    ("siglip_b", "linear", 10),       # optional
    "effv2_s_ft":      ("effv2_s", "finetune", 25),      # optional
}

def train(name):
    backbone, mode, epochs = RUNS[name]
    out = WORK / "runs" / name
    hist = out / "history.json"
    if DRY_RUN:
        backbone, epochs = "test", 3
    if (out / "best.pt").exists() and hist.exists() and len(json.loads(hist.read_text())) >= epochs:
        ok(f"{name} was already trained: skipping.")
        return
    cmd = [PY, "-m", "feature1_v2.train", "--backbone", backbone, "--mode", mode, "--epochs", epochs,
           "--out", out, "--resume"]
    if DRY_RUN:
        cmd += ["--img-size", "64", "--no-pretrained", "--workers", "0", "--ema", "0", "--batch", "16", "--lr", "3e-3"]
    else:
        cmd += ["--batch", "32", "--workers", "2", "--epoch-size", "20000"]
    t0 = time.time()
    sh(cmd)
    best = max(h["val_macro_f1"] for h in json.loads(hist.read_text()))
    ok(f"{name} finished in {(time.time() - t0) / 60:.0f} min (best validation score {best:.3f}). Go to the next box.")

print("Training helper ready. Go to the next box.")
''')
md("### 8a. Quick model: DINOv2-small, linear  (about 30–45 min)")
code('train("dinov2_s_lin")')
md("### 8b. Main model 1: DINOv2-small, full training  (about 2–3 h, probably over 2 sessions)")
code('train("dinov2_s_ft")')
md("### 8c. Main model 2: ConvNeXt-V2-tiny, full training  (about 2–3 h)")
code('train("convnextv2_t_ft")')
md("""
### 8d. Optional extra models
Only if you have time left, or Claude asks you to. Change `False` to `True` and press ▶.
""")
code(r'''
RUN_OPTIONAL = False
if RUN_OPTIONAL:
    train("siglip_b_lin")
    train("effv2_s_ft")
else:
    print("Skipped (optional).")
''')

md("""
## 9. Pick the winner: is the new model really better?  (10–20 min)
Each new model and the old one answer the **same** validation photos. "Sure range" is the 95 % confidence interval: if the whole range is above zero, the new model is better for real, not by luck.
""")
code(r'''
v1_pred = WORK / "v1_baseline" / "eval_val" / "predictions.csv"
table = []
for name in RUNS:
    ck = WORK / "runs" / name / "best.pt"
    if not ck.exists():
        continue
    ev = ck.parent / "eval_val" / "report.json"
    if not ev.exists() or ev.stat().st_mtime < ck.stat().st_mtime:
        sh([PY, "-m", "feature1_v2.evaluate", "--ckpt", ck, "--split", "val"])
    cmp_file = ck.parent / "compare_vs_v1.json"
    sh([PY, "-m", "feature1_v2.compare", v1_pred, ck.parent / "eval_val" / "predictions.csv", "--json", cmp_file])
    r = json.loads(ev.read_text())
    c = json.loads(cmp_file.read_text()).get("pred_crop_given")
    table.append((name, r["auto"]["accuracy"], r["crop_given"]["accuracy"], r["auto"]["macro_f1"], c))
if not table:
    fail("No trained model found yet. Run the boxes in section 8 first.")

print(f"\n{'model':18} {'correct':>8} {'crop known':>11} {'macro-F1':>9}   vs OLD model (crop known)")
for name, acc, accc, f1, c in table:
    if c:
        d, lo, hi = c["accuracy_diff"]
        versus = f"{d:+.1%}  (sure range {lo:+.1%} to {hi:+.1%})  → {c['verdict'].replace('B', 'NEW').replace('A', 'OLD')}"
    else:
        versus = "no shared photos"
    print(f"{name:18} {acc:8.1%} {accc:11.1%} {f1:9.3f}   {versus}")

winner = max(table, key=lambda t: (round(t[2], 3), round(t[1], 3), t[3]))   # crop known, then overall, then macro-F1
(WORK / "winner.txt").write_text(winner[0])
if winner[4] and winner[4]["verdict"] == "B better":
    ok(f"🏆 Winner: {winner[0]}. It is clearly better than the old model. Go to the next box.")
else:
    warn(f"The best new model ({winner[0]}) is NOT clearly better than the old one yet. "
         "Stop here, copy this table and send it to Claude.")
''')

md("""
## 10. Calibrate the winner  (5–10 min)
Teaches the app **when to answer and when to say "please retake the photo"**, so that when it does answer it is right about 90 % of the time.
""")
code(r'''
WIN = winner_dir()
sh([PY, "-m", "feature1_v2.calibrate", "--ckpt", WIN / "best.pt", "--target", "0.90", "--tta"])
sh([PY, "-m", "feature1_v2.evaluate", "--ckpt", WIN / "best.pt", "--split", "val", "--tta"])
cal = json.loads((WIN / "calibration.json").read_text())
print(f"\nWhen the user picks the crop: the app answers on {cal['val_coverage_crop']:.0%} of photos and is right on "
      f"{cal['val_accuracy_accepted_crop']:.0%} of those.")
print(f"When the app must guess the crop too: answers on {cal['val_coverage_auto']:.0%}, right on "
      f"{cal['val_accuracy_accepted_auto']:.0%}.")
print(f"Confidence honesty error (ECE, lower is better): {cal['ece_before']:.3f} before → {cal['ece_after']:.3f} after.")
ok("Calibrated. Go to the next box.")
''')

md("""
## 11. Optional: leaf finder  (about 1.5 h)
Trains a small model that finds the leaves in a photo, then checks whether it actually helps. Change `False` to `True` to run it. If the result says "do not use", that's fine: the app works without it.
""")
code(r'''
RUN_DETECTOR = False
if not RUN_DETECTOR or DRY_RUN:
    print("Skipped (optional).")
else:
    WIN = winner_dir()
    det_src = RAW / "PlantDoc-Object-Detection-Dataset"
    if not det_src.exists():
        sh(["git", "clone", "--depth", "1", "https://github.com/pratikkayal/PlantDoc-Object-Detection-Dataset", det_src])
    yolo_data = LOCAL / "detector" / "yolo"
    sh([PY, "-m", "feature1_v2.detector.prepare_plantdoc", "--src", det_src, "--out", yolo_data])
    runs = WORK / "detector" / "runs"
    best_w, last_w, done = (runs / "leaf" / "weights" / "best.pt", runs / "leaf" / "weights" / "last.pt",
                            runs / "leaf" / "FINISHED")
    if not done.exists():
        if last_w.exists():      # continue after a disconnect
            sh(["yolo", "detect", "train", "resume", f"model={last_w}"])
        else:
            sh(["yolo", "detect", "train", f"data={yolo_data / 'leaf.yaml'}", "model=yolov8n.pt", "imgsz=640",
                "epochs=80", f"project={runs}", "name=leaf", "exist_ok=True"])
        done.touch()
    sh([PY, "-m", "feature1_v2.detector.evaluate_gain", "--ckpt", WIN / "best.pt", "--detector", best_w])
    g = json.loads((WIN / "detector_gain.json").read_text())
    print(f"\nWithout leaf finder {g['accuracy_without_detector']:.1%}, with it {g['accuracy_with_detector']:.1%}")
    ok(f"Decision: {g['decision']}")
''')

md("""
## 12. ⚠️ FINAL EXAM (run only ONCE, at the very end)
Tests the old and new model on the locked exam photos. **Only do this when all training is finished.** Every run is written in a log, so the results stay honest.

To run it, change `I_AM_SURE = False` to `I_AM_SURE = True` and press ▶.
""")
code(r'''
I_AM_SURE = False or DRY_RUN
final = WORK / "final_exam.json"
if final.exists():
    ok("The final exam was already done. Results:")
    print(final.read_text())
elif not I_AM_SURE:
    print("Not run. Change I_AM_SURE = False to True when all training is finished.")
else:
    WIN = winner_dir()
    win_name = WIN.name
    sh([PY, "-m", "feature1_v2.evaluate", "--legacy", V1, "--split", "test", "--final", "--purpose", "final exam: old model v6p2"])
    sh([PY, "-m", "feature1_v2.evaluate", "--ckpt", WIN / "best.pt", "--split", "test", "--final", "--tta",
        "--purpose", f"final exam: new model {win_name}"])
    sh([PY, "-m", "feature1_v2.compare", WORK / "v1_baseline" / "eval_test" / "predictions.csv",
                    WIN / "eval_test" / "predictions.csv", "--json", WORK / "final_compare.json"])
    old = json.loads((WORK / "v1_baseline" / "eval_test" / "report.json").read_text())
    new = json.loads((WIN / "eval_test" / "report.json").read_text())
    res = {"old": {"auto": old["auto"]["accuracy"], "crop_given": old["crop_given"]["accuracy"]},
           "new": {"model": win_name, "auto": new["auto"]["accuracy"], "crop_given": new["crop_given"]["accuracy"],
                   "macro_f1": new["auto"]["macro_f1"]},
           "compare": json.loads((WORK / "final_compare.json").read_text())}
    final.write_text(json.dumps(res, indent=1, default=float))
    print(f"\nFINAL EXAM  old model {old['auto']['accuracy']:.1%} (crop known {old['crop_given']['accuracy']:.1%})"
          f"  →  new model {new['auto']['accuracy']:.1%} (crop known {new['crop_given']['accuracy']:.1%})")
    ok("Final exam done. Go to the last box.")
''')

md("""
## 13. Pack the results for Claude  (1 min)
Makes **`results_to_send.zip`** in your Drive folder `sgreen`. Send it to Claude, or upload it to the chat.
""")
code(r'''
out_zip = D / "results_to_send.zip"
win_dir = WORK / "runs" / (WORK / "winner.txt").read_text().strip() if (WORK / "winner.txt").exists() else None
with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(WORK.rglob("*")):
        rel = f.relative_to(WORK)
        small = f.suffix in (".json", ".md", ".txt") and f.stat().st_size < 5_000_000
        if f.is_file() and small and "detector/yolo" not in str(rel):
            z.write(f, Path("work") / rel)
    for f in sorted(BENCH.glob("*")):
        z.write(f, Path("benchmark") / f.name)
    if win_dir is not None:
        for name in ("best.pt", "calibration.json"):
            if (win_dir / name).exists():
                z.write(win_dir / name, Path("model") / name)
ok(f"Packed: {out_zip}  ({out_zip.stat().st_size / 1e6:.0f} MB). Send this file to Claude. 🎉")
''')


def main():
    nb = nbf.v4.new_notebook()
    nb["cells"] = CELLS
    nb["metadata"] = {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4"},
                      "kernelspec": {"name": "python3", "display_name": "Python 3"},
                      "language_info": {"name": "python"}}
    path = HERE / "train_feature1_v2.ipynb"
    nbf.write(nb, path)
    print(path)


if __name__ == "__main__":
    main()
