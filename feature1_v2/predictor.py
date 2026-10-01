"""
The Feature 1 v2 prediction service (plan, Steps 2, 3.3-3.5).

    p = Predictor("work/runs/best/best.pt", detector="work/detector/best.pt")
    result = p.predict([img1, img2], crop="tomato")       # crop optional

What it does, in order
  1. leaf detection (optional): find leaves in each photo and classify each
     leaf crop as well as the whole photo
  2. logits for every view (test-time augmentation: flips)
  3. crop selector: if the user gave the crop, only that crop's conditions compete
  4. several photos / leaves -> one answer:
       "mean"  average log-probabilities (photos of the same plant)
       "worst" a disease seen confidently on any leaf wins over "healthy"
  5. temperature-scaled confidence, then accept / reject:
       - "not a supported leaf"  (unsupported class or energy above threshold)
       - "low confidence"        (below the calibrated threshold for that mode)
  6. look-alike hint when the top two conditions are close
"""

from pathlib import Path

import numpy as np
from PIL import Image

from feature1_v2 import inference, models, taxonomy

LOOKALIKE_MARGIN = 0.20     # top-2 probability gap below which both are shown as look-alikes


class Predictor:
    def __init__(self, ckpt, detector=None, tta=True, calibration=None):
        self.model, ck = models.load_checkpoint(ckpt)
        self.model.to(inference.device())
        self.classes, self.meta = ck["classes"], ck["meta"]
        cal_path = Path(calibration) if calibration else Path(ckpt).with_name("calibration.json")
        import json
        self.cal = json.loads(cal_path.read_text()) if cal_path.exists() else {
            "temperature": 1.0, "threshold_auto": 0.7, "threshold_crop": 0.7, "energy_threshold": float("inf")}
        self.tta = tta
        self.detector = None
        if detector:
            from feature1_v2.detector.leaf_detector import LeafDetector
            self.detector = LeafDetector(detector) if isinstance(detector, (str, Path)) else detector

    @property
    def crops(self):
        return sorted({taxonomy.crop_of(c) for c in self.classes if c != taxonomy.UNSUPPORTED})

    def _views(self, images):
        """Whole photos plus detected leaf crops. Returns (list of PIL, list of 'photo'/'leaf')."""
        views, kinds = [], []
        for im in images:
            im = im.convert("RGB")
            views.append(im)
            kinds.append("photo")
            if self.detector is not None:
                for box in self.detector.leaves(im):
                    views.append(im.crop(box))
                    kinds.append("leaf")
        return views, kinds

    def predict(self, images, crop=None, aggregate=None):
        if isinstance(images, (Image.Image, str, Path)):
            images = [images]
        images = [Image.open(i) if isinstance(i, (str, Path)) else i for i in images]
        if crop is not None and crop not in self.crops:
            raise ValueError(f"crop '{crop}' is not supported by this model; supported: {self.crops}")
        T = self.cal["temperature"]
        views, kinds = self._views(images)
        z = inference.logits_for_images(self.model, views, self.meta, tta=self.tta)

        # 1. "not a supported leaf": judged on the whole photos, before any crop restriction
        photo_z = z[[i for i, k in enumerate(kinds) if k == "photo"]]
        p_photo = inference.aggregate_photos(photo_z, T)
        unsup_i = self.classes.index(taxonomy.UNSUPPORTED) if taxonomy.UNSUPPORTED in self.classes else None
        energy = float(np.mean(inference.energy(photo_z, T)))
        top_unsup = unsup_i is not None and int(p_photo.argmax()) == unsup_i
        if crop is None and (top_unsup or energy > self.cal["energy_threshold"]):
            return self._result(False, None, float(p_photo.max()), p_photo, crop, len(images), kinds, energy,
                                "not_supported",
                                "This does not look like a leaf of a supported crop. Supported crops: "
                                + ", ".join(taxonomy.CROPS[c][0] for c in self.crops) + ".")

        # 2. crop restriction and aggregation over photos / leaves
        zz = inference.restrict_to_crop(z, self.classes, crop) if crop else z.copy()
        if unsup_i is not None:
            zz[:, unsup_i] = -np.inf                          # unsupported was handled above
        mode = aggregate or ("worst" if "leaf" in kinds else "mean")
        if mode == "worst":
            probs = inference.softmax(zz, T)
            best = None
            for p in probs:
                c = int(p.argmax())
                if taxonomy.condition_of(self.classes[c]) != "healthy" and (best is None or p[c] > best[c]):
                    best = p
            p_final = best if best is not None and best.max() >= self._threshold(crop) else inference.aggregate_photos(zz, T)
        else:
            p_final = inference.aggregate_photos(zz, T)

        conf = float(p_final.max())
        if conf < self._threshold(crop):
            return self._result(False, None, conf, p_final, crop, len(images), kinds, energy, "low_confidence",
                                "The model is not confident enough. Retake the photo: one leaf filling the frame, "
                                "daylight, in focus; or add 1-2 more photos of the same plant.")
        return self._result(True, self.classes[int(p_final.argmax())], conf, p_final, crop, len(images), kinds,
                            energy, None, None)

    def _threshold(self, crop):
        return self.cal["threshold_crop"] if crop else self.cal["threshold_auto"]

    def _result(self, accepted, label, conf, probs, crop, n_photos, kinds, energy, reason_code, reason):
        order = np.argsort(-probs)
        alts = [{"label": self.classes[i], "en": taxonomy.display(self.classes[i], "en"),
                 "ar": taxonomy.display(self.classes[i], "ar"), "probability": round(float(probs[i]), 4)}
                for i in order[:3] if np.isfinite(probs[i]) and probs[i] > 0]
        lookalike = None
        if accepted and len(alts) > 1 and alts[0]["probability"] - alts[1]["probability"] < LOOKALIKE_MARGIN:
            lookalike = [alts[0]["label"], alts[1]["label"]]
        return {
            "accepted": accepted,
            "prediction": label,
            "crop": taxonomy.crop_of(label) if label else crop,
            "condition": taxonomy.condition_of(label) if label else None,
            "display": {"en": taxonomy.display(label, "en"), "ar": taxonomy.display(label, "ar")} if label else None,
            "confidence": round(conf, 4),
            "crop_given_by_user": crop is not None,
            "alternatives": alts,
            "lookalike": lookalike,
            "rejection_code": reason_code,
            "rejection_reason": reason,
            "photos": n_photos,
            "leaves_detected": sum(k == "leaf" for k in kinds),
            "energy": round(energy, 3),
        }
