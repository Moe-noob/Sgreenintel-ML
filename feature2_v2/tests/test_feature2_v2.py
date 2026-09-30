"""
Evidence suite for Feature 2 v2.   Run:  python -m unittest discover feature2_v2/tests -v

A. Reproduction of the published KSU model (Elnesr & Alazba 2016):
   every computed column of the spreadsheet for all 365 sowing days,
   its date windows and best day, and the paper's model-efficiency tables.
B. FAO-56 / FAO-29 worked examples and formula checks.
C. Data integrity (stations inside KSA, crop rows intact).
D. Model behaviour (season length responds to temperature correctly).
E. Agreement with well-established KSA growing practice.
"""

import datetime as dt
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import advisor                      # noqa: E402
import agronomy                     # noqa: E402
import climate                      # noqa: E402
import elnesr_model as em           # noqa: E402
import season                       # noqa: E402
from crops import ksa_crops, load_crop_table   # noqa: E402


class A_SpreadsheetReproduction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = json.loads((HERE / "data" / "spreadsheet_fixture.json").read_text(encoding="utf-8"))
        st = cls.fx["station"]
        cls.res = em.run({k: st[k] for k in ("Tx", "Tn", "Ta", "ET0")}, cls.fx["params"])

    def test_constants(self):
        p = self.fx["params"]
        self.assertAlmostEqual(self.res["kc_eq"], p["kc_eq_sheet"], places=12)
        self.assertEqual(self.res["hu_min"], p["hu_min_sheet"])
        self.assertEqual(self.res["hu_max"], p["hu_max_sheet"])

    def test_all_365_rows_all_columns(self):
        checked = 0
        for mine, xl in zip(self.res["rows"], self.fx["rows"]):
            for key, v in xl.items():
                if isinstance(v, (int, float)):
                    self.assertAlmostEqual(mine[key], v, places=9, msg=f"doy {xl['doy']} {key}")
                    checked += 1
        self.assertGreater(checked, 365 * 20)

    def test_windows_and_best_day(self):
        s = self.fx["summary"]
        self.assertEqual([list(w) for w in self.res["hu_windows"]], s["hu_windows"])
        self.assertEqual([list(w) for w in self.res["hu_temp_windows"]], s["hu_temp_windows"])
        self.assertEqual(self.res["n_hu_days"], s["n_hu_days"])
        self.assertEqual(self.res["n_hu_temp_days"], s["n_hu_temp_days"])
        self.assertEqual(self.res["max_comb_idx_hu"], s["max_comb_idx_hu_sum"])
        self.assertEqual(self.res["max_comb_idx_hu_temp"], s["max_comb_idx_hu_temp_sum"])
        self.assertEqual(self.res["best_doy"], 199)   # Excel shows serial 199 as "Jul-17"

    def test_integral_matches_summation(self):
        """Paper Sec. 3.1: the integral and summation forms agree closely."""
        diffs = [abs(r["hu_int"] - r["hu_sum"]) / r["hu_sum"] for r in self.res["rows"] if r["hu_int"]]
        self.assertLess(max(diffs), 0.05)


class A_OverlapEfficiency(unittest.TestCase):
    """Paper Table 1 (Central Maryland): relative sizes -> published efficiencies."""
    TABLE1 = [  # crop, Xs, Vs, Ns, published overall efficiency %
        ("Asparagus", 1.0, .70, 0, 91), ("Beans, Lima", .36, .70, 0, 70), ("Beets", .63, .00, .37, 64),
        ("Cabbage", .46, .03, .51, 50), ("Spinach", .42, .04, .54, 47), ("Sweet potatoes", 1.0, 2.68, 0, 67),
        ("Tomatoes", .99, .33, 0, 95), ("Garlic", .13, .45, .42, 39), ("Watermelon", .81, 2.28, 0, 65),
    ]

    def test_table1(self):
        cases = [{"Xs": x, "Vs": v, "Ns": n} for _, x, v, n, _ in self.TABLE1]
        for (crop, *_, pub), r in zip(self.TABLE1, em.overlap_efficiency(cases)):
            self.assertLessEqual(abs(r["omega_mean"] - pub), 1.0, crop)

    def test_sets(self):
        o = em.overlap_sets(range(10, 30), range(20, 40))
        self.assertEqual((o["X"], o["V"], o["N"]), (10, 10, 10))


class B_FAOExamples(unittest.TestCase):
    def test_eq66_example28(self):
        st = (25, 25, 30, 20)
        for day, exp in [(20, 0.15), (40, 0.77), (70, 1.19), (95, 0.56)]:
            self.assertAlmostEqual(season.kc_on_day(day - 1, st, 0.15, 1.19, 0.35), exp, places=2)

    def test_eq62_example27(self):
        self.assertAlmostEqual(season.adjust_kc(1.20, 2.0, u2=4.6, rhmin=44), 1.30, places=2)
        self.assertAlmostEqual(season.adjust_kc(1.20, 2.0, u2=1.3, rhmin=75), 1.07, places=2)

    def test_leaching_fao29_eq7(self):
        lr, _ = agronomy.leaching_requirement("Potato", 1.2, "surface")
        self.assertAlmostEqual(lr, 1.2 / (5 * 1.7 - 1.2), places=6)

    def test_maas_hoffman(self):
        self.assertEqual(agronomy.salinity_yield_pct("Tomato", 0.5)["low"], 100.0)   # ECe 0.75 < 0.9
        y = agronomy.salinity_yield_pct("Tomato", 4.0)                             # ECe 6.0
        self.assertAlmostEqual(y["low"], 100 - 9.9 * (6.0 - 0.9))
        self.assertAlmostEqual(y["high"], 100 - 9.0 * (6.0 - 2.5))

    def test_p_adjustment_limits(self):
        self.assertAlmostEqual(agronomy.adjusted_p(0.40, 5.0), 0.40)
        self.assertEqual(agronomy.adjusted_p(0.40, 15.0), 0.10)


class B_Fao56Rev1(unittest.TestCase):
    """Values transcribed from FAO-56 Rev.1 (2025), spot-checked here against the printed tables."""

    def test_table_6_1_kc(self):
        self.assertEqual(agronomy.KC_REV1["Tomato"][:3], (0.60, 1.10, 1.00))
        self.assertEqual(agronomy.KC_REV1["Okra"][:3], (0.50, 0.95, 0.80))

    def test_table_8_1_p_and_8_8_salt(self):
        self.assertEqual(agronomy.ROOTING["Potato"][2], 0.40)
        self.assertEqual(agronomy.ROOTING["Spinach"][2], 0.25)
        self.assertEqual(agronomy.SALT_TOLERANCE["Garlic"][:4], (3.9, 3.9, 14.3, 14.3))

    def test_water_uses_rev1_but_paper_uses_1998(self):
        t = next(c for c in ksa_crops() if c["number"] == 34)
        self.assertEqual((t["kc_mid"], t["kc_end"]), (1.10, 1.00))
        p = em.params_from_crop(t)
        self.assertEqual((p["kc_mid"], p["kc_end"]), (1.15, 0.80))


class C_DataIntegrity(unittest.TestCase):
    def test_stations(self):
        doc = json.loads((HERE / "data" / "stations_ksa.json").read_text(encoding="utf-8"))
        names = " ".join(s["name"] for s in doc["stations"])
        for foreign in ("Kuwait", "Bahrain", "Azraq", "Irwaished", "Rum"):
            self.assertNotIn(foreign, names)
        self.assertEqual(len(doc["stations"]), 24)
        for s in doc["stations"]:
            self.assertTrue(16 < s["lat"] < 33 and 34 < s["lon"] < 56)

    def test_crop_rows(self):
        table = load_crop_table()
        self.assertEqual(len(table), 122)
        self.assertEqual(table[1]["crop"], "Broccoli")
        for c in ksa_crops():
            self.assertAlmostEqual(c["hu_min_tab"], (c["t_opt"] - c["t_base"]) * c["dur_total"], delta=0.5)
            self.assertAlmostEqual(c["dur_total"], c["dur_ini"] + c["dur_dev"] + c["dur_mid"] + c["dur_late"], delta=0.5)

    def test_climate_is_physical(self):
        for s in climate.load_stations():
            sm = s.summary()
            self.assertTrue(25 < sm["tmax_hottest_c"] < 48, s.name)
            self.assertTrue(-2 < sm["tmin_coldest_c"] < 25, s.name)
            self.assertTrue(1200 < sm["et0_annual_mm"] < 3200, s.name)
            for j in range(1, 366):
                self.assertGreater(s.tx(j), s.tn(j))


class _ConstStation:
    """A synthetic station with constant weather, for behavioural tests."""
    def __init__(self, t):
        self.t = t

    def tx(self, j):
        return self.t + 5

    def tn(self, j):
        return self.t - 5

    def ta(self, j):
        return self.t

    def et0(self, j):
        return 5.0


class D_ModelBehaviour(unittest.TestCase):
    def setUp(self):
        self.tomato = next(c for c in ksa_crops() if c["number"] == 34)

    def test_rev1_gdd_stage_lengths(self):
        # Tomato (market), Rev.1 Table 6.11: 325/660/880/200 GDD, Tbase 7, Tupper 28.
        # At a constant 17 degC: 10 GDD/day -> 33/66/88/20 days (ceil of cumulative).
        L = season.stage_lengths(self.tomato, _ConstStation(17), 1)
        self.assertEqual(L, (33, 66, 88, 20))
        # Above the cap min(Tupper 28, Topt 24) = 24 degC the rate stays at 17 GDD/day
        self.assertEqual(sum(season.stage_lengths(self.tomato, _ConstStation(40), 1)), 122)
        self.assertEqual(sum(season.stage_lengths(self.tomato, _ConstStation(24), 1)), 122)

    def test_no_unrealistically_short_seasons(self):
        # Review finding: hot sowings once gave spinach 29 d, broccoli 42 d, garlic 56 d.
        floor = {"Spinach": 40, "Broccoli": 60, "Garlic": 90, "Squash": 55, "Beans, green": 50}
        for city in ("riyadh", "jazan", "hail", "tabuk"):
            st = climate.resolve(city)["station"]
            for c in ksa_crops():
                if c["key"] in floor:
                    r = advisor.analyse_crop(c, st)
                    if "best" in r:
                        self.assertGreaterEqual(r["best"]["total_days"], floor[c["key"]], f"{c['key']} @ {city}")

    def test_fallback_eq7_reproduces_fao56_at_optimum(self):
        okra = next(c for c in ksa_crops() if c["key"] == "Okra")
        self.assertNotIn("gdd_rev1", okra)
        L = season.stage_lengths(okra, _ConstStation(okra["t_opt"]), 1)
        self.assertEqual(L, tuple(int(okra[k]) for k in ("dur_ini", "dur_dev", "dur_mid", "dur_late")))

    def test_cooler_is_longer(self):
        warm = sum(season.stage_lengths(self.tomato, _ConstStation(24), 1))
        cool = sum(season.stage_lengths(self.tomato, _ConstStation(15), 1))
        self.assertGreater(cool, warm)

    def test_below_base_never_finishes(self):
        self.assertIsNone(season.stage_lengths(self.tomato, _ConstStation(6), 1))

    def test_water_totals_consistent(self):
        sim = season.simulate(self.tomato, _ConstStation(24), 1, detail=True)
        self.assertAlmostEqual(sim["season_etc_mm"], sum(d["etc"] for d in sim["daily"]), places=6)
        self.assertAlmostEqual(sim["season_etc_mm"], sum(s["etc_mm"] for s in sim["stages"]), places=6)
        # kc_eq x ET0 over the same stages equals the daily sum (Eq. 14-15 are exact for a linear Kc)
        t = self.tomato
        kc_eq = em.kc_equivalent(t["kc_ini"], t["kc_mid"], t["kc_end"], *sim["stage_lengths"])
        self.assertAlmostEqual(sim["season_etc_mm"], kc_eq * 5.0 * sim["total_days"], delta=1.0)


class F_Alsadon2002Benchmark(unittest.TestCase):
    """Directorate sowing dates, Alsadon (2002) Table 5 -- see validation/alsadon2002.py."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(HERE / "validation"))
        import alsadon2002
        cls.cases, cls.summary = alsadon2002.main(write=False)

    def test_best_date_hit_rate(self):
        # 11/16 with the current rule (see DOCUMENTATION.md sec. 6.5 for the history)
        self.assertGreaterEqual(self.summary["v2_best_date_hit_rate"], 11 / 16)

    def test_broad_window_overlap_beats_published_baselines(self):
        s = self.summary
        self.assertGreater(s["v2_in_time"]["mean_omega"], s["alsadon_program"]["mean_omega"])
        self.assertGreater(s["v2_in_time"]["mean_omega"], s["paper_hu"]["mean_omega"])


class E_KsaPractice(unittest.TestCase):
    """
    Broad, well-established facts about Saudi vegetable production, used as
    sanity checks (not tuning targets): the Tihama coast (Jazan, Jeddah) grows
    warm-season vegetables in its mild winter; the Asir highlands (Abha) grow
    them in spring/summer; cool-season crops inland (Riyadh, Qassim, Madinah)
    are sown in autumn-winter, never in the summer heat.
    """

    @classmethod
    def setUpClass(cls):
        cls.res = {c: advisor.advise(c) for c in ("jazan", "abha", "riyadh", "qassim", "madinah")}

    def best(self, city, key, row=None):
        for c in self.res[city]["crops"]:
            if c["crop"] == key and (row is None or c["workbook_row"] == row):
                return c
        raise KeyError(key)

    def month(self, c):
        return dt.date(2023, 1, 1).replace() + dt.timedelta(days=c["best"]["sow_doy"] - 1)

    def test_tihama_winter_tomato(self):
        c = self.best("jazan", "Tomato", 34)
        self.assertEqual(c["status"], "recommended")
        self.assertIn(self.month(c).month, (9, 10, 11, 12, 1))

    def test_asir_summer_tomato(self):
        c = self.best("abha", "Tomato", 34)
        self.assertNotEqual(c["status"], "not_suitable")
        self.assertIn(self.month(c).month, (3, 4, 5, 6))

    def test_inland_cool_season_crops_not_summer(self):
        for city in ("riyadh", "qassim", "madinah"):
            for key in ("Potato", "Lettuce", "Carrots", "Onions {dry}", "Garlic"):
                c = self.best(city, key)
                self.assertNotIn(self.month(c).month, (5, 6, 7), f"{key} @ {city}")

    def test_riyadh_potato_autumn_winter(self):
        c = self.best("riyadh", "Potato")
        self.assertNotEqual(c["status"], "not_suitable")
        self.assertIn(self.month(c).month, (9, 10, 11, 12, 1, 2))


if __name__ == "__main__":
    unittest.main()
