"""
Exact re-implementation of the Elnesr & Alazba (2016) planting-date model,
as the KSU spreadsheet (mmc1.xlsx, sheet "Model") actually computes it.

tests/test_spreadsheet_reproduction.py checks this module against the
values Excel cached in the shipped workbook for all 365 sowing days.

Paper equations -> code
-----------------------
Eq. 2   GDD_j   = max(0, (Tx_j + Tn_j)/2 - Tb)
Eq. 1   HU_s    = sum of GDD over the season                       (hu_sum)
Eq. 6   HU_s    = integral of the Ta sinusoid minus Tb             (hu_int)
Eq. 7   HU_min  = (Topt - Tb) * DUR
Eq. 8   HU_max  = (1 + Htol/100) * HU_min
Eq. 14  Kc_eq   = duration-weighted mean Kc of the 4 FAO-56 stages
Eq. 15  ET_s    = Kc_eq * seasonal ET0 (sum or integral)           (et_sum / et_int)
Eq. 16  I_ov    = beta * eta * (c * I_HU + (1 - c) * I_ET)
Eq. 17  I_HU    = 100 (HU - HU_n) / (HU_x - HU_n)
Eq. 18  I_ET    = 100 (1 - (ET - ET_n) / (ET_x - ET_n))

Spreadsheet details that differ from a literal reading of the paper
(reproduced here on purpose, and documented in README):
  * DUR is the crop's "DurTherm" column, not DUR_total.
  * The HU test is HU_min < HU <= HU_max (strict on the lower bound).
  * The temperature test (beta) looks at Tx / Tn of the SOWING DAY only.
  * The "best day" maximises the combined index over HU-suitable days
    (eta = 1), averaging tied days, i.e. beta is shown but not used there.
  * Eq. 12 in the paper prints "(a_E - Tb)"; the sheet uses a_E (no Tb),
    which is the correct integral of the ET0 sinusoid.
  * Values are rounded with Excel ROUND / ROUNDUP semantics.
"""

import math
from decimal import Decimal, ROUND_HALF_UP


def excel_round(x, digits=0):
    """Excel ROUND: half away from zero (Python's round() is half-to-even)."""
    q = Decimal(1).scaleb(-digits)
    d = Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP)
    return float(d)


def excel_roundup(x, digits=0):
    f = 10 ** digits
    return math.ceil(x * f - 1e-12) / f if x >= 0 else -math.ceil(-x * f - 1e-12) / f


def kc_equivalent(kc_ini, kc_mid, kc_end, d_ini, d_dev, d_mid, d_late):
    """Eq. 14 (sheet form: AVERAGE of the four stage products / AVERAGE of durations)."""
    num = kc_ini * d_ini + (kc_ini + kc_mid) / 2 * d_dev + kc_mid * d_mid + (kc_mid + kc_end) / 2 * d_late
    return num / (d_ini + d_dev + d_mid + d_late)


def _sin_integral(fit, j0, j1):
    return fit["a"] * (j1 - j0) - fit["rho"] / fit["omega"] * (
        math.cos(fit["omega"] * j1 + fit["phi"]) - math.cos(fit["omega"] * j0 + fit["phi"]))


def _sine(fit, j):
    return fit["a"] + fit["rho"] * math.sin(fit["omega"] * j + fit["phi"])


def _runs(days, flags):
    """Contiguous runs of flagged days -> list of (first_doy, last_doy)."""
    out, start, prev = [], None, None
    for d, f in zip(days, flags):
        if f and start is None:
            start = d
        if not f and start is not None:
            out.append((start, prev))
            start = None
        prev = d
    if start is not None:
        out.append((start, prev))
    return out


def run(fits, p):
    """
    fits: {"Tx","Tn","Ta","ET0"} -> {"a","rho","omega","phi"}
    p:    kc_ini, kc_mid, kc_end, dur_ini, dur_dev, dur_mid, dur_late,
          dur (season length for HU and ET), t_base, t_opt, t_max, t_min,
          heat_tol_pct, hu_weight (c in Eq. 16; sheet default slider = 0.75)
    Returns per-day rows (doy 1..365) and a summary.
    """
    dur = int(excel_round(p["dur"]))
    tb = p["t_base"]
    kc_eq = kc_equivalent(p["kc_ini"], p["kc_mid"], p["kc_end"],
                          p["dur_ini"], p["dur_dev"], p["dur_mid"], p["dur_late"])
    hu_min = excel_roundup((p["t_opt"] - tb) * dur)
    hu_max = excel_roundup((1 + p["heat_tol_pct"] / 100) * hu_min)

    n_days = 365 + dur
    tx = [None] + [_sine(fits["Tx"], j) for j in range(1, n_days + 1)]
    tn = [None] + [_sine(fits["Tn"], j) for j in range(1, n_days + 1)]
    ta = [None] + [(tx[j] + tn[j]) / 2 for j in range(1, n_days + 1)]
    et0 = [None] + [_sine(fits["ET0"], j) for j in range(1, n_days + 1)]
    gdd = [None] + [max(ta[j] - tb, 0.0) for j in range(1, n_days + 1)]

    rows = []
    for i in range(1, 366):
        q = i + dur
        et_sum = kc_eq * excel_round(sum(et0[i:i + dur]))
        hu_sum = excel_round(sum(gdd[i:i + dur]))
        et_int = kc_eq * excel_round(max(0.0, _sin_integral(fits["ET0"], i, q)))
        hu_int_raw = (fits["Ta"]["a"] - tb) * dur - fits["Ta"]["rho"] / fits["Ta"]["omega"] * (
            math.cos(fits["Ta"]["omega"] * q + fits["Ta"]["phi"]) - math.cos(fits["Ta"]["omega"] * i + fits["Ta"]["phi"]))
        hu_int = None if hu_int_raw < 0 else excel_round(hu_int_raw)
        flag_hu = 1 if (hu_sum > hu_min and not hu_sum > hu_max) else 0
        flag_tmax = 0 if tx[i] > p["t_max"] else 1
        flag_tmin = 0 if tn[i] < p["t_min"] else 1
        rows.append({"doy": i, "tx": tx[i], "tn": tn[i], "ta": ta[i], "et0": et0[i], "gdd": gdd[i],
                     "et_sum": et_sum, "hu_sum": hu_sum, "doy_harvest": q, "et_int": et_int, "hu_int": hu_int,
                     "flag_hu": flag_hu, "flag_tmax": flag_tmax, "flag_tmin": flag_tmin,
                     "flag_all": flag_hu * flag_tmax * flag_tmin})

    def rng(key):
        vals = [r[key] for r in rows if r[key] is not None]
        return min(vals), max(vals)

    w = p["hu_weight"]
    (etn, etx), (hun, hux) = rng("et_sum"), rng("hu_sum")
    (eitn, eitx), (huin, huix) = rng("et_int"), rng("hu_int")
    for r in rows:
        r["idx_et_sum"] = excel_round(100 - 100 * (r["et_sum"] - etn) / (etx - etn), 1)
        r["idx_hu_sum"] = excel_round(100 * (r["hu_sum"] - hun) / (hux - hun), 1)
        r["idx_comb_sum"] = r["idx_et_sum"] * (1 - w) + r["idx_hu_sum"] * w
        r["idx_et_int"] = excel_round(100 - 100 * (r["et_int"] - eitn) / (eitx - eitn), 1)
        r["idx_hu_int"] = None if r["hu_int"] is None else excel_round(100 * (r["hu_int"] - huin) / (huix - huin), 1)
        r["idx_comb_int"] = None if r["idx_hu_int"] is None else r["idx_et_int"] * (1 - w) + r["idx_hu_int"] * w

    hu_ok = [r for r in rows if r["flag_hu"]]
    best_doy = None
    if hu_ok:
        top = max(r["idx_comb_sum"] for r in hu_ok)
        tied = [r["doy"] for r in hu_ok if r["idx_comb_sum"] == top]
        best_doy = sum(tied) / len(tied)
    # Same selection restricted to the "yellow band" (HU and sowing-day temperature both
    # satisfied): the spreadsheet's column AL, whose maximum is Model!AL18.
    yellow = [r for r in rows if r["flag_all"]]
    best_doy_yellow = None
    if yellow:
        top_y = max(r["idx_comb_sum"] for r in yellow)
        tied_y = [r["doy"] for r in yellow if r["idx_comb_sum"] == top_y]
        best_doy_yellow = sum(tied_y) / len(tied_y)
    days = [r["doy"] for r in rows]
    return {
        "rows": rows,
        "kc_eq": kc_eq, "hu_min": hu_min, "hu_max": hu_max, "dur": dur,
        "hu_windows": _runs(days, [r["flag_hu"] for r in rows]),
        "hu_temp_windows": _runs(days, [r["flag_all"] for r in rows]),
        "n_hu_days": len(hu_ok), "n_hu_temp_days": sum(r["flag_all"] for r in rows),
        "best_doy": best_doy,
        "max_comb_idx_hu": max((r["idx_comb_sum"] for r in hu_ok), default=None),
        "best_doy_hu_temp": best_doy_yellow,
        "max_comb_idx_hu_temp": max((r["idx_comb_sum"] for r in yellow), default=None),
    }


def params_from_crop(crop, hu_weight=0.75, dur=None):
    """Build model parameters from a crops_eln16.json row (defaults as the sheet uses them)."""
    # the paper method always uses the workbook's own (FAO-56 1998) Kc values
    kc = lambda k: crop.get(k + "_1998", crop[k])
    return {"kc_ini": kc("kc_ini"), "kc_mid": kc("kc_mid"), "kc_end": kc("kc_end"),
            "dur_ini": crop["dur_ini"], "dur_dev": crop["dur_dev"], "dur_mid": crop["dur_mid"],
            "dur_late": crop["dur_late"], "dur": dur if dur is not None else crop["dur_therm"],
            "t_base": crop["t_base"], "t_opt": crop["t_opt"], "t_max": crop["t_max"], "t_min": crop["t_min"],
            "heat_tol_pct": crop["heat_tol_pct"], "hu_weight": hu_weight}


# ---------------------------------------------------------------------------
# Interval-overlap efficiency (paper Sec. 2.5, Eqs. 19-28)
# ---------------------------------------------------------------------------

def overlap_sets(model_days, observed_days):
    """Eqs. 19-24. Both arguments are sets of day-of-year integers."""
    m, b = set(model_days), set(observed_days)
    x, v, n = m & b, m - b, b - m
    return {"B": len(b), "M": len(m), "X": len(x), "V": len(v), "N": len(n),
            "Xs": len(x) / len(b), "Vs": len(v) / len(b), "Ns": len(n) / len(b)}


def overlap_efficiency(cases):
    """
    Eqs. 25-28 over a list of overlap_sets() results. The paper's text calls
    the overall efficiency a product (Eq. 28), but every row of its Tables 1
    and 2 equals the MEAN of the three partial efficiencies (e.g. Asparagus:
    (100 + 74 + 100) / 3 = 91). The tables are the published results, so the
    mean is used; the product is returned too.
    """
    xs_max = max(c["Xs"] for c in cases) or 1
    vs_max = max(c["Vs"] for c in cases) or 1
    ns_max = max(c["Ns"] for c in cases) or 1
    out = []
    for c in cases:
        xq = 100 * c["Xs"] / xs_max
        vq = 100 * (1 - c["Vs"] / vs_max)
        nq = 100 * (1 - c["Ns"] / ns_max)
        out.append({**c, "Xq": xq, "Vq": vq, "Nq": nq, "omega_mean": (xq + vq + nq) / 3,
                    "omega_product": xq * vq * nq / 1e4})
    return out
