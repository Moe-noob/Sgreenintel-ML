"""
Advice knowledge base (complete, bilingual, sourced), weather rules on
synthetic forecasts, season note, the combined service response and the
FastAPI router (stub model, so no real training is needed).
"""

import datetime as dt
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from feature1_v2 import models, taxonomy
from feature1_v2.advice import kb, season_check, weather_risk
from feature1_v2.advice.categories import CATEGORIES
from feature1_v2.advice.entries import ENTRIES
from feature1_v2.service import enrich
from feature1_v2.tests.test_predictor import CLASSES, StubModel, photo


def forecast(days, temp, rh, rain=0.0):
    """Hourly forecast: lists or callables of (day, hour)."""
    h = {"time": [], "temperature_2m": [], "relative_humidity_2m": [], "precipitation": []}
    for d in range(days):
        for hr in range(24):
            h["time"].append(f"2026-01-{d + 1:02d}T{hr:02d}:00")
            h["temperature_2m"].append(temp(d, hr) if callable(temp) else temp)
            h["relative_humidity_2m"].append(rh(d, hr) if callable(rh) else rh)
            h["precipitation"].append(rain(d, hr) if callable(rain) else rain)
    return h


class TestKnowledgeBase(unittest.TestCase):
    def test_complete_and_consistent(self):
        self.assertEqual(kb.validate(), [])
        labels = [l for l in taxonomy.all_labels() if l != taxonomy.UNSUPPORTED]
        self.assertEqual(set(labels), set(ENTRIES))

    def test_every_entry_bilingual_with_sources_and_label_rule(self):
        for lbl in ENTRIES:
            for lang in ("en", "ar"):
                a = kb.advice_for(lbl, lang)
                self.assertTrue(a["confirm_symptoms"] and a["immediate_steps"] and a["sources"], lbl)
                self.assertEqual(a["review_status"][:5], "draft")
                if a["chemical_control"]:
                    self.assertTrue(any(s["key"] == "mewa" for s in a["sources"]), lbl)
                    self.assertIn("MEWA" if lang == "en" else "وزارة البيئة", a["chemical_control"]["label_rule"])
            ar = kb.advice_for(lbl, "ar")
            self.assertTrue(any("؀" <= ch <= "ۿ" for ch in ar["confirm_symptoms"]), lbl)

    def test_no_product_names_or_doses(self):
        text = json.dumps(CATEGORIES, ensure_ascii=False) + json.dumps(ENTRIES, ensure_ascii=False)
        for bad in ("ml/l", "g/l", "kg/ha", "L/ha", "ml per", "grams per"):
            self.assertNotIn(bad, text)

    def test_oomycetes_and_bacteria_have_the_right_template(self):
        for lbl in ("tomato__late_blight", "potato__late_blight", "grape__downy_mildew", "lettuce__downy_mildew",
                    "broccoli__downy_mildew"):
            self.assertEqual(ENTRIES[lbl]["category"], "oomycete", lbl)
        for lbl in ("tomato__bacterial_spot", "bell_pepper__bacterial_spot", "strawberry__angular_leaf_spot",
                    "cucumber__angular_leaf_spot", "bean__halo_blight"):
            self.assertEqual(ENTRIES[lbl]["category"], "bacterial", lbl)
        for lbl, e in ENTRIES.items():
            if e["category"].startswith("virus"):
                self.assertIn("no cure", CATEGORIES[e["category"]]["name"]["en"])

    def test_lookalike_hint(self):
        h = kb.lookalike_hint(["tomato__early_blight", "tomato__late_blight"], "en")
        self.assertEqual(len(h), 2)
        self.assertIn("rings", h[0]["check_for"])


class TestWeatherRules(unittest.TestCase):
    def test_hutton_period(self):
        humid = forecast(4, 12.0, lambda d, h: 95 if h < 8 else 70)        # 8 h >= 90 %, Tmin 12
        r = weather_risk.assess("hutton_late_blight", humid)
        self.assertEqual(r["risk"], "high")
        self.assertEqual(len(r["events"]), 3)                              # day pairs 1-2, 2-3, 3-4
        cold = forecast(4, lambda d, h: 8.0 if h == 3 else 14.0, lambda d, h: 95 if h < 8 else 70)
        self.assertEqual(weather_risk.assess("hutton_late_blight", cold)["risk"], "low")
        short = forecast(4, 12.0, lambda d, h: 95 if h < 5 else 70)         # only 5 h humid
        self.assertEqual(weather_risk.assess("hutton_late_blight", short)["risk"], "low")
        one_day = forecast(4, 12.0, lambda d, h: 95 if (d == 1 and h < 8) else 60)
        self.assertEqual(weather_risk.assess("hutton_late_blight", one_day)["risk"], "low")

    def test_three_tens(self):
        wet = forecast(3, 15.0, 80, lambda d, h: 2.0 if d == 1 and 5 <= h < 11 else 0.0)   # 12 mm
        r = weather_risk.assess("three_tens_downy_mildew", wet, "ar")
        self.assertEqual(r["risk"], "high")
        self.assertEqual(len(r["events"]), 1)
        cold = forecast(3, 8.0, 80, lambda d, h: 2.0 if d == 1 and 5 <= h < 11 else 0.0)
        self.assertEqual(weather_risk.assess("three_tens_downy_mildew", cold)["risk"], "low")
        dry = forecast(3, 15.0, 80, lambda d, h: 1.0 if d == 1 and h < 8 else 0.0)        # 8 mm
        self.assertEqual(weather_risk.assess("three_tens_downy_mildew", dry)["risk"], "low")

    def test_no_rule(self):
        self.assertEqual(weather_risk.assess(None, None)["risk"], "not_available")


class TestSeasonNote(unittest.TestCase):
    def test_lettuce_riyadh(self):
        self.assertEqual(season_check.check("lettuce", "riyadh", dt.date(2026, 1, 15))["status"], "in_season")
        self.assertEqual(season_check.check("lettuce", "riyadh", dt.date(2026, 7, 15))["status"], "unusual_for_season")
        self.assertEqual(season_check.check("grape", "riyadh")["status"], "not_available")


class TestServiceAndApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        m, meta = models.create("test", len(CLASSES), img_size=64, pretrained=False)
        cls.ckpt = cls.tmp / "best.pt"
        models.save_checkpoint(cls.ckpt, m, meta, CLASSES)
        (cls.tmp / "calibration.json").write_text(json.dumps(
            {"temperature": 1.0, "threshold_auto": 0.6, "threshold_crop": 0.6, "energy_threshold": 1e9}))
        cls.meta = meta

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def service(self):
        from feature1_v2.service import Service
        s = Service(self.ckpt, tta=False)
        s.predictor.model = StubModel(self.meta["mean"], self.meta["std"])
        return s

    def test_enrich(self):
        pred = self.service().predictor.predict(photo(40), crop="tomato")
        humid = forecast(3, 12.0, lambda d, h: 95 if h < 8 else 70)
        out = enrich(pred, "ar", location="abha", date=dt.date(2026, 1, 10), hourly=humid)
        self.assertEqual(out["advice"]["category"], "oomycete")
        self.assertEqual(out["weather_risk"]["risk"], "high")
        self.assertIn(out["season_note"]["status"], ("in_season", "unusual_for_season"))
        rejected = self.service().predictor.predict(photo(80))
        self.assertIsNone(enrich(rejected)["advice"])

    def test_api(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from feature1_v2 import api_router
        api_router._service = self.service()
        app = FastAPI()
        app.include_router(api_router.router)
        c = TestClient(app)
        try:
            self.assertEqual([x["key"] for x in c.get("/v2/disease/crops").json()["crops"]], ["cucumber", "tomato"])
            buf = io.BytesIO()
            photo(200).save(buf, "JPEG")
            files = [("files", ("a.jpg", buf.getvalue(), "image/jpeg"))]
            r = c.post("/v2/disease/predict", files=files, data={"crop": "tomato", "lang": "ar", "weather": "false"})
            self.assertEqual(r.status_code, 200, r.text)
            body = r.json()
            self.assertEqual(body["prediction"]["prediction"], "tomato__healthy")
            self.assertEqual(body["advice"]["category"], "healthy")
            self.assertEqual(c.post("/v2/disease/predict", files=files, data={"crop": "date_palm"}).status_code, 400)
            self.assertEqual(c.post("/v2/disease/predict", files=files * 4).status_code, 400)
            bad = [("files", ("a.txt", b"hello", "text/plain"))]
            self.assertEqual(c.post("/v2/disease/predict", files=bad).status_code, 400)
            self.assertEqual(c.get("/v2/disease/advice/tomato__leaf_mold?lang=en").json()["category"], "fungal_leaf_spot")
            self.assertEqual(c.get("/v2/disease/advice/nope").status_code, 404)
        finally:
            api_router._service = None


if __name__ == "__main__":
    unittest.main()
