# How to train the new plant-disease model (beginner guide)

> **بالعربي باختصار:** اضغط ملفات البيانات الأربعة وارفعها مع ملف النموذج القديم إلى مجلد اسمه `sgreen` في Google Drive، ثم افتح دفتر Colab واضغط ▶ على كل خانة بالترتيب من الأعلى إلى الأسفل. ✅ تعني أن الخطوة نجحت، و❌ تشرح لك ماذا تفعل. إذا انقطع الاتصال فلن يضيع شيء: أعد تشغيل الخانات 0 إلى 4 ثم الخانة التي توقفت عندها.

You don't need to understand machine learning to do this. You will:
1. put 5 files in Google Drive (Part A, about 30 min, once);
2. open one notebook in Google Colab (Part B, 2 min);
3. press ▶ on each box from top to bottom and wait (Part C);
4. send the results file back to Claude (Part F).

Total: about 1 hour of setup, then mostly waiting while the GPU trains (2–3 sessions of 2–4 hours). You can close the laptop lid only if the browser tab keeps running. Easiest is to leave the tab open while it trains.

---

## Part A: On your computer (once)

You need these 4 things from the project folder where you trained the old model. They are not on GitHub because they are too big.

| What | Where it is on your PC |
|---|---|
| PlantWild photos | `Sgreenintel-ML/data/raw/plantwild` |
| PlantDoc photos | `Sgreenintel-ML/data/raw/PlantDoc-Dataset` |
| Old training photos | `Sgreenintel-ML/data/processed_v2` |
| Old model file | `Sgreenintel-ML/models/cnn/mobilenetv2_sgreenintel_v6p2.pth` |

**A1. Zip the 3 photo folders.**
- **Windows:** right-click the folder → **Send to** → **Compressed (zipped) folder**. (Windows 11: right-click → **Compress to ZIP file**.)
- **Mac:** right-click the folder → **Compress "…"**.

Zip the folder itself, not the files inside it. You should end up with exactly these names (rename if needed):
- `plantwild.zip`
- `PlantDoc-Dataset.zip`
- `processed_v2.zip`

Zipping thousands of photos takes a few minutes per folder. That's normal.

**A2. Download the code as a zip.**
1. Open the project on GitHub.
2. Switch the branch (the button that says `main`) to **`claude/compassionate-hopper-lh08ol`**.
3. Click the green **Code** button → **Download ZIP**.
4. Rename the downloaded file to **`code.zip`**.

**A3. Upload to Google Drive.**
1. Go to drive.google.com → **My Drive** → **New** → **New folder** → name it **`sgreen`** (small letters, nothing else).
2. Open it and upload 5 files: the 4 zips + `mobilenetv2_sgreenintel_v6p2.pth` (not zipped).
3. Wait until the upload says it's complete. Big zips can take a while on slow internet.

Your `sgreen` folder must look like this:

```
sgreen/
  code.zip
  plantwild.zip
  PlantDoc-Dataset.zip
  processed_v2.zip
  mobilenetv2_sgreenintel_v6p2.pth
```

**Space check:** the free Drive has 15 GB. You need the size of the 5 files plus about 3 GB for results. If Drive is nearly full, delete old stuff first.

## Part B: Open the notebook (2 min)

1. Unzip `code.zip` on your computer. Inside, find `feature1_v2/colab/train_feature1_v2.ipynb`.
2. Go to **colab.research.google.com** → **File** → **Upload notebook** → choose that `.ipynb` file.
3. In the Colab menu: **Runtime** → **Change runtime type** → **T4 GPU** → **Save**.

## Part C: Run the boxes, top to bottom

Press ▶ on a box, wait until it finishes (the ▶ stops spinning), then read the last line.

| Box | What it does | Time | ✅ looks like |
|---|---|---|---|
| 0 Settings | loads settings | 1 s | `Settings loaded.` |
| 1 GPU | checks you have a GPU | 10 s | `✅ GPU found: Tesla T4` |
| 2 Drive | connects Google Drive (click **Allow** in the pop-up) | 30 s | `✅ Google Drive connected` |
| 3 Unpack | copies code and photos to Colab | 10–20 min first time | `✅ Everything is unpacked` |
| 4 Install | installs extra software | 2–3 min | `✅ Software ready` |
| 5 Self-test | 37 automatic checks | 1 min | `✅ All checks passed` |
| 6 Prepare | lists photos, removes duplicates, locks the final exam | 20–40 min, **once** | a table of crops and `✅ … Final exam locked` |
| 7 Old model | scores the old model | 5 min | `Old model on real validation photos: 6x %` |
| 8a–8c Training | trains 3 new models | 45 min / 2–3 h / 2–3 h | `✅ dinov2_s_ft finished …` |
| 8d Optional | 2 extra models | skip unless asked | `Skipped (optional).` |
| 9 Winner | compares new vs old on the same photos | 10–20 min | `🏆 Winner: …` |
| 10 Calibrate | teaches the app when to say "retake the photo" | 5–10 min | `✅ Calibrated` |
| 11 Leaf finder | optional extra | skip, or ~1.5 h | `Skipped (optional).` |
| 12 Final exam | **only once, at the very end** (set `I_AM_SURE = True`) | 10 min | `✅ Final exam done` |
| 13 Pack | makes `results_to_send.zip` in your Drive | 1 min | `✅ Packed …` |

**What the training output means.** While a model trains you see one line per *epoch* (one learning round), for example:

```
{"epoch": 7, "train_loss": 0.83, "val_accuracy": 0.74, "val_macro_f1": 0.69, "seconds": 241.3}
```

`val_accuracy` is the share of validation photos it got right (0.74 = 74 %). It should mostly go **up**, with small wobbles. `train_loss` should mostly go **down**.

### When you see ❌

| Message says | Do this |
|---|---|
| `No GPU` | Runtime → Change runtime type → T4 GPU → Save, then start again from box 0 |
| `can't find the folder …/sgreen` | the Drive folder name must be exactly `sgreen`, inside **My Drive** |
| `These files are missing` | it lists the missing names: fix the name or upload the file, then run box 3 again |
| `… does not contain what I expected` | you zipped the wrong folder, or the files inside it instead of the folder: redo A1 for that one |
| `The step above stopped with an error` | scroll up, copy the last ~20 lines (especially lines with `Error`) and send them to Claude |
| `NOT clearly better` (box 9) | not your fault: stop and send the table to Claude, who will decide the next experiment |
| "You cannot currently connect to a GPU due to usage limits" (Colab pop-up) | the free GPU quota is used up for today: try again tomorrow. Your progress is saved |

## Part D: Colab disconnected? (it will, on the free plan)

Free Colab stops after a few hours, or when the tab is idle too long. **Nothing important is lost**: results and half-trained models are saved in your Drive (`sgreen/f1v2_work`).

1. Reconnect: the **Connect** button at the top right, or reopen the notebook.
2. Make sure the runtime is still **T4 GPU** (Part B, step 3).
3. Run boxes **0, 1, 2, 3, 4** again (about 10 min).
4. Press ▶ on the box where you stopped. Training says `resuming from epoch N` and continues. Finished steps say `already … skipping`.

Tip: keep the Colab tab in front now and then. Very long idle times make free Colab disconnect sooner.

## Part E: Two rules that keep the test honest

1. **Don't run box 12 (final exam) until all training is finished.** It is the one test the models never learn from or get chosen on. That is what makes the final number trustworthy. Every run is logged.
2. **Never delete `sgreen/f1v2_benchmark`.** It is the locked list of exam photos.

## Part F: Send the results to Claude

After box 13, download `sgreen/results_to_send.zip` from Drive and upload it in the chat with Claude, or simply paste the tables printed by boxes 6, 7, 9, 10 and 12.

Claude will then:
- fill the results into `DOCUMENTATION.md` and save the locked exam list in the project;
- if you want, connect the new model to the app (the `/v2/disease/...` API and the crop selector on the upload screen).

To use the model on your own computer: from the zip, put `model/best.pt` and `model/calibration.json` together in `feature1_v2/work/runs/best/`.

---

## Glossary (10 words you will see)

| Word | Meaning |
|---|---|
| **GPU** | a graphics chip that makes training ~50× faster than a normal processor |
| **Runtime** | the temporary computer Google lends you in Colab; it is wiped when it disconnects |
| **Epoch** | one learning round; training repeats many rounds |
| **Training photos** | photos the model learns from |
| **Validation photos** | photos used to compare models and choose settings; the model never learns from them |
| **Benchmark / final exam** | locked photos used once at the end to report the real score |
| **Accuracy** | share of photos answered correctly |
| **Macro-F1** | a score that treats rare diseases as important as common ones (0–1, higher is better) |
| **Sure range (95 % confidence interval)** | the range the true difference very likely lies in; if it's all above 0, the new model is really better |
| **Calibration** | adjusting the model's confidence so that "90 % sure" really means right 9 times out of 10 |
| **Checkpoint (`.pt`)** | the saved trained model file |
