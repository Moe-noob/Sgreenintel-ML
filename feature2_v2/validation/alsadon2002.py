"""
Benchmark against Saudi ground truth: Alsadon (2002), Table 5.

Source
  Alsadon, A.A. (2002). "The best planting dates for vegetable crops in Saudi
  Arabia: evaluation of compatibility between the dates planned based on heat
  units and dates suggested from the regional offices of the Ministry of
  Agriculture and Water." J. King Saud Univ. (Agric. Sci.) 14:75-97.
  (Arabic: السعدون، مواعيد زراعة محاصيل الخضر ... ، مجلة جامعة الملك سعود)

Table 5 gives, for 16 crop x region cases, the sowing dates recommended by the
regional Directorates of Agriculture & Water (the "observed" farmer-practice
calendar, B) and the dates from Alsadon's own heat-unit program (a published
baseline). Both are transcribed below with the original Arabic text.

Scored models (each gives a set of sowing days M):
  alsadon_program   Alsadon's heat-unit program (from the same table)
  paper_hu          exact Elnesr & Alazba (2016) spreadsheet, heat-unit window
  paper_hu_temp     same, heat units + sowing-day temperature ("yellow band")
  v2_in_time        v2 dates on which the crop finishes in time (broad tier)
  v2_low_stress     v2 dates with negligible temperature stress (strict tier)
  best dates        v2's single recommended date and the paper's best day
                    (hit = the date falls inside B)

Metrics (per case, then averaged):
  precision = |M n B| / |M|   share of the model's window the directorate agrees
                               with (Alsadon's own "% agreement" definition)
  recall    = |M n B| / |B|   share of the directorate window the model covers
  omega     = Elnesr & Alazba (2016) interval-overlap efficiency (Eqs. 19-28)

Run:  python feature2_v2/validation/alsadon2002.py
"""

import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import climate                          # noqa: E402
import elnesr_model as em               # noqa: E402
from advisor import analyse_crop, NEGLIGIBLE_STRESS_DD   # noqa: E402
from crops import load_crop_table, prepare               # noqa: E402

# Region -> (lat, lon) of the regional centre. Al-Ahsa (Hofuf) has no
# FAOCLIM-2 station; the nearest (Qatif, ~125 km) is used and flagged.
REGIONS = {"Tabuk": (28.38, 36.57), "Al-Ahsa": (25.38, 49.59), "Qassim": (26.33, 43.98), "Jazan": (16.89, 42.55)}

# (region, crop, workbook rows, directorate dates B, Alsadon program dates, Arabic B, Arabic program, published n/%)
# Date ranges are (month, day) inclusive; a bare month means the whole month.
CASES = [
    ("Tabuk", "Potato", [70], [((2, 1), (2, 28)), ((8, 1), (9, 30))], [((1, 15), (2, 28)), ((9, 1), (9, 30))],
     "فبراير، أغسطس- سبتمبر", "15 يناير- 28 فبراير، 1-30 سبتمبر", (4, 40)),
    ("Tabuk", "Squash", [47], [((3, 1), (4, 30)), ((7, 1), (8, 31))], [((4, 1), (8, 15))],
     "مارس، إبريل، يوليو، أغسطس", "1 إبريل - 15 أغسطس", (5, 55.6)),
    ("Tabuk", "Tomato", [34, 37], [((4, 1), (5, 31)), ((7, 1), (8, 31))], [((3, 1), (4, 15)), ((8, 1), (8, 30))],
     "أبريل- مايو، يوليو- أغسطس", "1 مارس- 15 إبريل، 1- 30 أغسطس", (3, 60)),
    ("Tabuk", "Watermelon", [54], [((3, 1), (4, 30)), ((7, 1), (7, 31))], [((5, 15), (6, 15))],
     "مارس- إبريل، يوليو", "15 مايو- 15 يونيو", (0, 0)),
    ("Al-Ahsa", "EggPlant", [30], [((2, 15), (3, 15)), ((7, 15), (8, 30))], [((2, 1), (2, 28)), ((8, 15), (9, 15))],
     "15 فبراير- 15 مارس، 15 يوليو- 30 أغسطس", "1-30 فبراير، 15 أغسطس- 15 سبتمبر", (2, 50)),
    ("Al-Ahsa", "Onions {dry}", [20], [((9, 1), (10, 31))], [((12, 15), (1, 15)), ((9, 1), (9, 30))],
     "سبتمبر- أكتوبر", "15 ديسمبر- 15يناير، 1-30 سبتمبر", (2, 66.7)),
    ("Al-Ahsa", "Tomato", [34, 37], [((8, 1), (10, 15))], [((2, 1), (2, 28)), ((9, 1), (9, 30))],
     "أغسطس- 15 أكتوبر", "1-30 فبراير، 1-30 سبتمبر", (2, 50)),
    ("Al-Ahsa", "Watermelon", [54], [((2, 1), (8, 31))], [((3, 15), (3, 30)), ((7, 15), (7, 30))],
     "فبراير- أغسطس", "15-30 مارس، 15-30 يوليو", (2, 20)),
    ("Qassim", "Pumpkin", [45], [((3, 1), (8, 31))], [((2, 15), (3, 15)), ((8, 1), (8, 30))],
     "مارس- أغسطس (القرع)", "15 فبراير- 15 مارس، 1 - 30 أغسطس", (3, 75)),
    ("Qassim", "Beans, green", [86], [((3, 1), (9, 30))], [((3, 1), (3, 30)), ((8, 15), (8, 30))],
     "مارس- سبتمبر (الفاصوليا)", "1- 30 مارس، 15- 30 أغسطس", (2, 66.7)),
    ("Qassim", "Lettuce", [17], [((9, 1), (10, 31))], [((1, 1), (1, 30)), ((10, 1), (10, 15))],
     "سبتمبر- أكتوبر", "1-30 يناير، 1-15 أكتوبر", (1, 33.3)),
    ("Qassim", "Tomato", [34, 37], [((1, 1), (3, 31))], [((2, 15), (3, 15)), ((9, 1), (9, 15))],
     "يناير- مارس", "15 فبراير- 15 مارس، 1-15 سبتمبر", (2, 66.7)),
    ("Jazan", "Cucumber {Fresh Market}", [42, 41], [((9, 1), (11, 30)), ((1, 1), (1, 31))], [((9, 15), (1, 30))],
     "سبتمبر- نوفمبر، يناير", "15 سبتمبر - 30 يناير", (7, 77.8)),
    ("Jazan", "Okra", [29], [((9, 1), (7, 15))], [((3, 1), (5, 15)), ((7, 15), (9, 15))],
     "سبتمبر- 15 يوليو", "1 مارس- 15 مايو، 15 يوليو- 15 سبتمبر", (8, 88.9)),
    ("Jazan", "Sweet peppers {bell}", [33], [((10, 1), (12, 31))], [((10, 15), (1, 30))],
     "أكتوبر- ديسمبر", "15 أكتوبر- 30 يناير", (5, 71.4)),
    ("Jazan", "Watermelon", [54], [((7, 1), (7, 31)), ((11, 1), (12, 31))], [((2, 15), (4, 30)), ((6, 15), (8, 30))],
     "يوليو، نوفمبر- ديسمبر", "15 فبراير- 30 إبريل، 15 يونيو- 30 أغسطس", (2, 20)),
]


def _doy(m, d):
    d = min(d, [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return dt.date(2023, m, d).timetuple().tm_yday


def days(ranges):
    out = set()
    for (m0, d0), (m1, d1) in ranges:
        a, b = _doy(m0, d0), _doy(m1, d1)
        span = range(a, b + 1) if a <= b else list(range(a, 366)) + list(range(1, b + 1))
        out.update(span)
    return out


def _runs_to_days(runs):
    s = set()
    for a, b in runs:
        s.update(range(a, b + 1))
    return s


def model_sets(region, rows):
    """Union over the crop's workbook rows (e.g. spring + autumn tomato)."""
    st = climate.resolve(REGIONS[region])["station"]
    table = load_crop_table()
    out = {"paper_hu": set(), "paper_hu_temp": set(), "v2_in_time": set(), "v2_low_stress": set(),
           "v2_best": [], "paper_best": []}
    for r in rows:
        crop = prepare(table[r])
        paper = em.run({k: st.fit(k) for k in ("Tx", "Tn", "Ta", "ET0")}, em.params_from_crop(crop))
        out["paper_hu"] |= _runs_to_days(paper["hu_windows"])
        out["paper_hu_temp"] |= _runs_to_days(paper["hu_temp_windows"])
        if paper["best_doy"]:
            out["paper_best"].append(int(round(paper["best_doy"])))
        res = analyse_crop(crop, st)
        out["v2_in_time"] |= {x["doy"] for x in res["by_sowing_day"] if x["candidate"]}
        out["v2_low_stress"] |= {x["doy"] for x in res["by_sowing_day"]
                                 if x["candidate"] and x["stress_dd"] <= NEGLIGIBLE_STRESS_DD}
        if "best" in res:
            out["v2_best"].append((res["best"]["sow_doy"], res["best"]["stress_dd"]))
    return st, out


def score(m, b):
    x = m & b
    return {"M": len(m), "B": len(b), "X": len(x),
            "precision": len(x) / len(m) if m else None, "recall": len(x) / len(b),
            "Xs": len(x) / len(b), "Vs": len(m - b) / len(b), "Ns": len(b - m) / len(b)}


def main(write=True):
    models = ["alsadon_program", "paper_hu", "paper_hu_temp", "v2_in_time", "v2_low_stress"]
    per_case, sets_for_omega = [], {k: [] for k in models}
    for region, crop, rows, b_rng, prog_rng, b_ar, prog_ar, published in CASES:
        b = days(b_rng)
        st, ms = model_sets(region, rows)
        ms["alsadon_program"] = days(prog_rng)
        row = {"region": region, "crop": crop, "station": st.name, "directorate": b_ar, "published_agreement": published}
        for k in models:
            row[k] = score(ms[k], b)
            sets_for_omega[k].append(row[k])
        # best date: as for the paper method, a hit if any of the crop's rows (e.g. spring or autumn tomato) is in B
        row["v2_best_doys"] = [d for d, _ in ms["v2_best"]]
        row["v2_best_in_B"] = any(d in b for d in row["v2_best_doys"])
        # the paper method has no preference between rows; count a hit if any row's best day is in B
        row["paper_best_in_B"] = any(d in b for d in ms["paper_best"])
        per_case.append(row)

    summary = {}
    for k in models:
        eff = em.overlap_efficiency([c for c in sets_for_omega[k]])
        prec = [c["precision"] for c in sets_for_omega[k] if c["precision"] is not None]
        summary[k] = {"mean_precision": sum(prec) / len(prec) if prec else None,
                      "cases_with_a_window": len(prec),
                      "mean_recall": sum(c["recall"] for c in sets_for_omega[k]) / len(CASES),
                      "mean_omega": sum(e["omega_mean"] for e in eff) / len(eff)}
    hits = sum(r["v2_best_in_B"] for r in per_case)
    summary["v2_best_date_hit_rate"] = hits / len(CASES)
    summary["paper_best_date_hit_rate"] = sum(r["paper_best_in_B"] for r in per_case) / len(CASES)

    print(f"{'region':8} {'crop':24} " + " ".join(f"{k[:14]:>15}" for k in models) + "  v2 best date")
    print(f"{'':33}" + " ".join(f"{'prec/recall':>15}" for _ in models))
    for r in per_case:
        cells = []
        for k in models:
            p = r[k]["precision"]
            cells.append(f"{('-' if p is None else f'{p:.0%}')}/{r[k]['recall']:.0%}".rjust(15))
        bd = ",".join((dt.date(2023, 1, 1) + dt.timedelta(days=d - 1)).strftime("%b %d") for d in r["v2_best_doys"]) or "none"
        print(f"{r['region']:8} {r['crop'][:24]:24} " + " ".join(cells) + f"  {bd} {'IN' if r['v2_best_in_B'] else 'out'}")
    print()
    for k in models:
        s = summary[k]
        mp = "-" if s["mean_precision"] is None else f"{s['mean_precision']:.0%}"
        print(f"{k:16} precision {mp:>4} (over {s['cases_with_a_window']:2} cases with a window)  "
              f"recall {s['mean_recall']:.0%}  omega {s['mean_omega']:.0f}%")
    print(f"best sowing date inside the directorate window: v2 {hits}/{len(CASES)}, "
          f"paper method {sum(r['paper_best_in_B'] for r in per_case)}/{len(CASES)}")
    if write:
        out = HERE / "alsadon2002_results.json"
        out.write_text(json.dumps({"cases": per_case, "summary": summary}, ensure_ascii=False, indent=1))
    return per_case, summary


if __name__ == "__main__":
    main()
