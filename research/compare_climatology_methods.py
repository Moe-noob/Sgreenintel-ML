"""
Standalone comparison: harmonic (Fourier) regression vs. the existing
moving-average climatology in nasa_power.py.

Does NOT modify nasa_power.py or any other existing file. Reuses only
fetch_daily_raw() (a read-only API call) and the existing field-name /
fill-value constants, imported directly to stay perfectly consistent
with the production pipeline's parsing logic.

Method: fits value ~ a0 + a1*cos(wt) + b1*sin(wt) + a2*cos(2wt) + b2*sin(2wt)
(w = 2*pi/365, t = day-of-year) via ordinary least squares
(numpy.linalg.lstsq) to all ~3650 raw daily observations at once, for
each of the 7 climate variables independently. This is a closed-form
linear regression, not a trained/tuned model -- two harmonics (annual +
semi-annual cycle) is the standard choice in atmospheric science for
fitting a seasonal cycle, not a value tuned against this data.

Usage:
    python heatmap\\compare_climatology_methods.py
"""

import sys
from pathlib import Path
from collections import defaultdict

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "heatmap"))

from nasa_power import (
    fetch_daily_raw, build_daily_climatology, _doy_365,
    FIELDS, _POWER_TO_FIELD, FILL_VALUE_THRESHOLD, _radiation_to_mj,
)

N_HARMONICS = 2  # annual + semi-annual cycle -- standard in atmospheric science
DOY_TEST_POINTS = [15, 105, 196, 288]  # same days nasa_power.py's own self-test checks

CACHE_DIR = Path(__file__).resolve().parent / "cache"


def _raw_payload_cached(lat, lon):
    """Simple local cache for this comparison script only -- avoids
    re-hitting NASA POWER on repeated runs while testing. Separate
    cache file from nasa_power.py's own cache, so nothing collides.
    Filename includes the date range (matching nasa_power.py's own
    cache-naming pattern) so a changed DAILY_START/DAILY_END never
    silently serves a stale window."""
    import json
    from nasa_power import DAILY_START, DAILY_END
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"raw_payload_{lat:.2f}_{lon:.2f}_{DAILY_START}_{DAILY_END}.json"
    if path.exists():
        with open(path) as fh:
            return json.load(fh)
    payload = fetch_daily_raw(lat, lon)
    with open(path, "w") as fh:
        json.dump(payload, fh)
    return payload


def build_all_field_raw_years(payload):
    """
    Like nasa_power.py's raw_years, but for ALL 7 fields (not just
    Tmax/Tmin), needed for a fair full-field harmonic comparison.
    Returns: {field: [(doy, value), ...]} across all years, fill
    values already dropped.
    """
    raw = payload["properties"]["parameter"]
    rad_unit = (payload.get("parameters", {}).get("ALLSKY_SFC_SW_DWN", {}) or {}).get("units", "")

    by_field = defaultdict(list)
    for power_name, field in _POWER_TO_FIELD.items():
        series = raw[power_name]
        for date_key, value in series.items():
            if value is None or value <= FILL_VALUE_THRESHOLD:
                continue
            if field == "solar_radiation_mj":
                value = _radiation_to_mj(value, rad_unit)
            doy = _doy_365(date_key)
            by_field[field].append((doy, value))
    return by_field


def fit_harmonic(doy_value_pairs, n_harmonics=N_HARMONICS):
    """
    Fits a Fourier series to (day_of_year, value) pairs via ordinary
    least squares. Returns (coefficients, r_squared).
    """
    doys = np.array([d for d, v in doy_value_pairs], dtype=float)
    values = np.array([v for d, v in doy_value_pairs], dtype=float)
    t = 2 * np.pi * doys / 365.0

    columns = [np.ones_like(t)]
    for h in range(1, n_harmonics + 1):
        columns.append(np.cos(h * t))
        columns.append(np.sin(h * t))
    X = np.column_stack(columns)

    coeffs, residuals, rank, sv = np.linalg.lstsq(X, values, rcond=None)

    predicted = X @ coeffs
    ss_res = np.sum((values - predicted) ** 2)
    ss_tot = np.sum((values - values.mean()) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    return coeffs, r_squared


def evaluate_harmonic(coeffs, doy, n_harmonics=N_HARMONICS):
    """Evaluates a fitted Fourier series at a specific day-of-year."""
    t = 2 * np.pi * doy / 365.0
    value = coeffs[0]
    idx = 1
    for h in range(1, n_harmonics + 1):
        value += coeffs[idx] * np.cos(h * t)
        value += coeffs[idx + 1] * np.sin(h * t)
        idx += 2
    return value


def build_harmonic_climatology(payload):
    """Fits all 7 fields, returns a 365-entry list matching the
    existing climatology's structure exactly, plus per-field R²."""
    by_field = build_all_field_raw_years(payload)

    fitted = {}
    r_squared = {}
    for field in FIELDS:
        coeffs, r2 = fit_harmonic(by_field[field])
        fitted[field] = coeffs
        r_squared[field] = r2

    clim = []
    for doy in range(1, 366):
        entry = {"doy": doy}
        for field in FIELDS:
            entry[field] = float(evaluate_harmonic(fitted[field], doy))
        clim.append(entry)

    return clim, r_squared


def compare(lat, lon, label):
    print(f"\n{'='*78}")
    print(f"  {label}  ({lat}, {lon})")
    print(f"{'='*78}")

    payload = _raw_payload_cached(lat, lon)

    print("\nFitting existing moving-average climatology...")
    ma_clim, meta = build_daily_climatology(payload)

    print("Fitting harmonic regression climatology...")
    hr_clim, r_squared = build_harmonic_climatology(payload)

    print(f"\nHarmonic regression goodness of fit (R²) per field:")
    for field, r2 in r_squared.items():
        print(f"  {field:20s} R² = {r2:.3f}")
    print("  (R² close to 1.0 means the smooth curve explains most of the day-to-day")
    print("   variation; values well below 1.0 are expected for noisy fields like")
    print("   precipitation, which genuinely isn't well described by a smooth seasonal curve)")

    print(f"\nSide-by-side at the same test days nasa_power.py's own self-test checks:")
    print(f"{'DOY':>5} {'Field':<18} {'Moving-avg':>12} {'Harmonic':>12} {'Diff':>8}")
    for doy in DOY_TEST_POINTS:
        ma = ma_clim[doy - 1]
        hr = hr_clim[doy - 1]
        for field in ["temp_c", "temp_max_c", "temp_min_c", "wind_speed_ms"]:
            print(f"{doy:>5} {field:<18} {ma[field]:>12.2f} {hr[field]:>12.2f} {hr[field]-ma[field]:>8.2f}")
        print()

    print("Mean absolute difference across all 365 days, per field:")
    for field in FIELDS:
        diffs = [abs(hr_clim[i][field] - ma_clim[i][field]) for i in range(365)]
        print(f"  {field:20s} mean |diff| = {sum(diffs)/365:.3f}")

    print("\nYear-boundary continuity check (Dec 31 -> Jan 1), temp_c:")
    print(f"  Moving-avg:  Dec 31 = {ma_clim[364]['temp_c']:.3f}   Jan 1 = {ma_clim[0]['temp_c']:.3f}   "
          f"jump = {abs(ma_clim[364]['temp_c'] - ma_clim[0]['temp_c']):.3f}")
    print(f"  Harmonic:    Dec 31 = {hr_clim[364]['temp_c']:.3f}   Jan 1 = {hr_clim[0]['temp_c']:.3f}   "
          f"jump = {abs(hr_clim[364]['temp_c'] - hr_clim[0]['temp_c']):.3f}")

    return r_squared


def compare_all_cities(cities):
    """
    Runs the R² fit (harmonic regression, 2 harmonics) for every city
    and prints a summary table -- checks whether the temperature-good/
    wind-dewpoint-precip-poor pattern found for Riyadh/Abha generalizes
    across Saudi Arabia's different climate zones (interior desert,
    coastal, highland, northern), rather than resting on 2 cities.
    """
    print(f"\n{'#'*78}")
    print(f"  MULTI-CITY SUMMARY: R² per field, all {len(cities)} known cities")
    print(f"{'#'*78}\n")

    all_r2 = {field: [] for field in FIELDS}
    per_city = {}

    for name, (lat, lon) in cities.items():
        payload = _raw_payload_cached(lat, lon)
        by_field = build_all_field_raw_years(payload)
        r2_row = {}
        for field in FIELDS:
            _, r2 = fit_harmonic(by_field[field])
            r2_row[field] = r2
            all_r2[field].append(r2)
        per_city[name] = r2_row
        print(f"  {name:10s} " + "  ".join(f"{f.split('_')[0][:4]}={r2_row[f]:.2f}" for f in FIELDS))

    print(f"\n  {'AVERAGE':10s} " + "  ".join(
        f"{f.split('_')[0][:4]}={sum(all_r2[f])/len(all_r2[f]):.2f}" for f in FIELDS))
    print(f"\nField key: temp=temp_c, temp=temp_max_c/temp_min_c (both start 'temp'), "
          f"dewp=dewpoint_c, wind=wind_speed_ms, sola=solar_radiation_mj, prec=precip_mm_day")


def sweep_harmonics(lat, lon, label, fields_to_test, harmonic_counts=(1, 2, 3, 4, 5)):
    """
    Tests whether R² keeps improving as more harmonics are added, or
    plateaus early. If a field's R² barely moves from 1 harmonic to 5,
    that's evidence the field genuinely isn't well-described by ANY
    smooth periodic curve -- not just under-fit by our choice of 2.
    """
    print(f"\n{'-'*78}")
    print(f"  HARMONIC COUNT SWEEP -- {label}")
    print(f"{'-'*78}\n")

    payload = _raw_payload_cached(lat, lon)
    by_field = build_all_field_raw_years(payload)

    print(f"{'Field':<20}" + "".join(f"{'H='+str(h):>8}" for h in harmonic_counts))
    for field in fields_to_test:
        row = []
        for h in harmonic_counts:
            _, r2 = fit_harmonic(by_field[field], n_harmonics=h)
            row.append(r2)
        print(f"{field:<20}" + "".join(f"{r2:>8.3f}" for r2 in row))


def build_field_date_value(payload):
    """
    Like build_all_field_raw_years, but keyed by the actual date string
    (not just day-of-year) so we can determine which year each
    observation belongs to -- needed to hold out a specific year for
    cross-validation.
    Returns: {field: {date_key: value}}, fill values already dropped,
    radiation already converted to MJ.
    """
    raw = payload["properties"]["parameter"]
    rad_unit = (payload.get("parameters", {}).get("ALLSKY_SFC_SW_DWN", {}) or {}).get("units", "")

    by_field = {}
    for power_name, field in _POWER_TO_FIELD.items():
        series = raw[power_name]
        field_data = {}
        for date_key, value in series.items():
            if value is None or value <= FILL_VALUE_THRESHOLD:
                continue
            if field == "solar_radiation_mj":
                value = _radiation_to_mj(value, rad_unit)
            field_data[date_key] = value
        by_field[field] = field_data
    return by_field


def build_moving_average_from_subset(by_field_date_value, excluded_year):
    """
    Refits the moving-average climatology using every year EXCEPT
    excluded_year -- exactly mirrors nasa_power.py's own
    build_daily_climatology() logic (same smoothing window, same
    circular wraparound), just restricted to a 9-year subset, so the
    comparison against harmonic regression is a fair, like-for-like
    refit rather than comparing a 10-year fit to a 9-year fit.
    """
    from nasa_power import SMOOTHING_HALF_WINDOW, _smooth_circular

    sums = {f: defaultdict(float) for f in FIELDS}
    counts = {f: defaultdict(int) for f in FIELDS}

    for field in FIELDS:
        for date_key, value in by_field_date_value[field].items():
            if date_key[:4] == excluded_year:
                continue
            doy = _doy_365(date_key)
            sums[field][doy] += value
            counts[field][doy] += 1

    clim = []
    for doy in range(1, 366):
        entry = {"doy": doy}
        for f in FIELDS:
            entry[f] = sums[f][doy] / counts[f][doy]
        clim.append(entry)

    for f in FIELDS:
        smoothed = _smooth_circular([c[f] for c in clim], SMOOTHING_HALF_WINDOW)
        for c, v in zip(clim, smoothed):
            c[f] = v

    return clim


def build_raw_doy_means_from_subset(by_field_date_value, excluded_year):
    """
    Per-day-of-year mean across all years except excluded_year, BEFORE
    any smoothing -- shared by the moving-average and Gaussian methods,
    so the only difference tested between them is the smoothing kernel
    itself (uniform box-car vs. Gaussian-weighted), not the underlying
    per-day averages.
    """
    sums = {f: defaultdict(float) for f in FIELDS}
    counts = {f: defaultdict(int) for f in FIELDS}
    for field in FIELDS:
        for date_key, value in by_field_date_value[field].items():
            if date_key[:4] == excluded_year:
                continue
            doy = _doy_365(date_key)
            sums[field][doy] += value
            counts[field][doy] += 1
    return {f: [sums[f][doy] / counts[f][doy] for doy in range(1, 366)] for f in FIELDS}


def gaussian_smooth_circular(values, sigma=5.0, half_window=None):
    """
    Gaussian-weighted circular smoothing: same idea as the existing
    method's uniform +/-7-day box-car average, but weights nearby days
    more than distant ones instead of an equal-weight hard cutoff at
    the window edge.

    sigma=5.0 gives an effective spread of about +/-15 days (3 sigma),
    matching the existing method's ~15-day-wide window -- chosen for a
    fair comparison, not tuned against this project's own data.
    """
    import math
    n = len(values)
    if half_window is None:
        half_window = int(round(3 * sigma))
    offsets = list(range(-half_window, half_window + 1))
    weights = [math.exp(-0.5 * (o / sigma) ** 2) for o in offsets]
    total_w = sum(weights)

    smoothed = []
    for i in range(n):
        s = sum(values[(i + o) % n] * w for o, w in zip(offsets, weights))
        smoothed.append(s / total_w)
    return smoothed


def build_gaussian_climatology_from_subset(by_field_date_value, excluded_year, sigma=5.0):
    """Gaussian-weighted equivalent of build_moving_average_from_subset."""
    raw_means = build_raw_doy_means_from_subset(by_field_date_value, excluded_year)
    smoothed_by_field = {f: gaussian_smooth_circular(raw_means[f], sigma) for f in FIELDS}
    clim = []
    for doy in range(1, 366):
        entry = {"doy": doy}
        for f in FIELDS:
            entry[f] = smoothed_by_field[f][doy - 1]
        clim.append(entry)
    return clim


def fit_loess_circular(doy_value_pairs, frac=None):
    """
    Fits LOESS (locally weighted regression, statsmodels' standard
    implementation) to (day_of_year, value) pairs.

    Handles the year's circular boundary by tripling the data (shifted
    -365, 0, +365) before fitting -- the standard trick for periodic
    LOESS, so Dec 31 -> Jan 1 is treated as adjacent, not a break,
    without needing custom wraparound code.

    frac defaults to a window matching the existing method's ~15-day-
    wide smoothing, for a fair comparison, not tuned against this data.

    Returns (sorted_x, sorted_y) -- evaluate with evaluate_loess().
    """
    from statsmodels.nonparametric.smoothers_lowess import lowess

    doys = np.array([d for d, v in doy_value_pairs], dtype=float)
    values = np.array([v for d, v in doy_value_pairs], dtype=float)

    tripled_x = np.concatenate([doys - 365, doys, doys + 365])
    tripled_y = np.concatenate([values, values, values])

    if frac is None:
        target_window_days = 15
        frac = target_window_days / (3 * 365)

    result = lowess(tripled_y, tripled_x, frac=frac, it=0, return_sorted=True)
    return result[:, 0], result[:, 1]


def evaluate_loess(fitted_xy, doy):
    sorted_x, sorted_y = fitted_xy
    return float(np.interp(doy, sorted_x, sorted_y))


def cross_validate(lat, lon, label, fields=("temp_c", "temp_max_c", "temp_min_c",
                                             "wind_speed_ms", "dewpoint_c",
                                             "solar_radiation_mj", "precip_mm_day")):
    """
    Leave-one-year-out cross-validation across FOUR methods: the
    existing moving-average (uniform box-car), harmonic regression,
    Gaussian-weighted smoothing, and LOESS. Each is refit on 9 years
    and checked against the real observed values in the held-out 10th
    year, repeated for all 10 years -- genuine held-out accuracy for
    every method, on identical folds, for a fully fair comparison.
    """
    print(f"\n{'='*90}")
    print(f"  LEAVE-ONE-YEAR-OUT CROSS-VALIDATION (4 methods) -- {label}")
    print(f"{'='*90}")

    payload = _raw_payload_cached(lat, lon)
    by_field_date_value = build_field_date_value(payload)
    years = sorted(set(dk[:4] for dk in by_field_date_value["temp_c"].keys()))
    print(f"\n  Years available: {years}")

    errors = {method: {f: [] for f in fields} for method in ["moving_avg", "harmonic", "gaussian", "loess"]}

    for held_out_year in years:
        ma_clim = build_moving_average_from_subset(by_field_date_value, held_out_year)
        ga_clim = build_gaussian_climatology_from_subset(by_field_date_value, held_out_year)

        for field in fields:
            train_pairs = [
                (_doy_365(dk), v) for dk, v in by_field_date_value[field].items()
                if dk[:4] != held_out_year
            ]
            hr_coeffs, _ = fit_harmonic(train_pairs)
            lo_fit = fit_loess_circular(train_pairs)

            for date_key, actual in by_field_date_value[field].items():
                if date_key[:4] != held_out_year:
                    continue
                doy = _doy_365(date_key)
                errors["moving_avg"][field].append(abs(ma_clim[doy - 1][field] - actual))
                errors["harmonic"][field].append(abs(evaluate_harmonic(hr_coeffs, doy) - actual))
                errors["gaussian"][field].append(abs(ga_clim[doy - 1][field] - actual))
                errors["loess"][field].append(abs(evaluate_loess(lo_fit, doy) - actual))

    print(f"\n  Cross-validated MAE against real held-out years (lower = more accurate):")
    print(f"  {'Field':<20}{'Moving-avg':>13}{'Harmonic':>13}{'Gaussian':>13}{'LOESS':>13}{'Winner':>13}")
    results = {}
    for field in fields:
        maes = {m: sum(errors[m][field]) / len(errors[m][field]) for m in errors}
        winner = min(maes, key=maes.get)
        print(f"  {field:<20}{maes['moving_avg']:>13.4f}{maes['harmonic']:>13.4f}"
              f"{maes['gaussian']:>13.4f}{maes['loess']:>13.4f}{winner:>13}")
        results[field] = maes

    return results


def cross_validate_all_cities(cities, fields=("temp_c", "temp_max_c", "temp_min_c")):
    """
    Runs the 4-method leave-one-year-out CV for every known city and
    summarizes win counts -- checks whether any method wins consistently
    across Saudi Arabia's different climate zones.
    """
    print(f"\n{'#'*90}")
    print(f"  MULTI-CITY CROSS-VALIDATION SUMMARY (4 methods, temperature fields)")
    print(f"{'#'*90}")

    all_maes = {f: {m: [] for m in ["moving_avg", "harmonic", "gaussian", "loess"]} for f in fields}
    wins = {f: {"moving_avg": 0, "harmonic": 0, "gaussian": 0, "loess": 0} for f in fields}

    for name, (lat, lon) in cities.items():
        payload = _raw_payload_cached(lat, lon)
        by_field_date_value = build_field_date_value(payload)
        years = sorted(set(dk[:4] for dk in by_field_date_value["temp_c"].keys()))

        errors = {method: {f: [] for f in fields} for method in ["moving_avg", "harmonic", "gaussian", "loess"]}

        for held_out_year in years:
            ma_clim = build_moving_average_from_subset(by_field_date_value, held_out_year)
            ga_clim = build_gaussian_climatology_from_subset(by_field_date_value, held_out_year)
            for field in fields:
                train_pairs = [
                    (_doy_365(dk), v) for dk, v in by_field_date_value[field].items()
                    if dk[:4] != held_out_year
                ]
                hr_coeffs, _ = fit_harmonic(train_pairs)
                lo_fit = fit_loess_circular(train_pairs)
                for date_key, actual in by_field_date_value[field].items():
                    if date_key[:4] != held_out_year:
                        continue
                    doy = _doy_365(date_key)
                    errors["moving_avg"][field].append(abs(ma_clim[doy - 1][field] - actual))
                    errors["harmonic"][field].append(abs(evaluate_harmonic(hr_coeffs, doy) - actual))
                    errors["gaussian"][field].append(abs(ga_clim[doy - 1][field] - actual))
                    errors["loess"][field].append(abs(evaluate_loess(lo_fit, doy) - actual))

        row = []
        for field in fields:
            maes = {m: sum(errors[m][field]) / len(errors[m][field]) for m in errors}
            for m in maes:
                all_maes[field][m].append(maes[m])
            winner = min(maes, key=maes.get)
            wins[field][winner] += 1
            row.append(f"{field.split('_')[0][:4]}:[{winner[:4]}]")
        print(f"  {name:10s} " + "  ".join(row))

    print(f"\n  Wins out of {len(cities)} cities, and average MAE per method:")
    for field in fields:
        print(f"\n  {field}:")
        print(f"    Wins:    " + "  ".join(f"{m}={wins[field][m]}" for m in wins[field]))
        avgs = {m: sum(all_maes[field][m]) / len(all_maes[field][m]) for m in all_maes[field]}
        print(f"    Avg MAE: " + "  ".join(f"{m}={avgs[m]:.4f}" for m in avgs))


def sweep_gaussian_sigma(lat, lon, label, fields=("temp_c", "temp_max_c", "temp_min_c"),
                         sigma_values=(2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0)):
    """
    Tests whether sigma=5.0 (chosen to roughly match the existing
    method's ~15-day window) was actually a good choice, or just a
    reasonable-looking default -- same leave-one-year-out CV used
    everywhere else, swept across sigma instead of comparing methods.

    If MAE stays flat across a wide sigma range, the method is robust
    to this choice (our earlier conclusion isn't an artifact of picking
    a lucky sigma). If one sigma is clearly better, that's new,
    actionable information.
    """
    print(f"\n{'-'*90}")
    print(f"  GAUSSIAN SIGMA SWEEP -- {label}")
    print(f"{'-'*90}\n")

    payload = _raw_payload_cached(lat, lon)
    by_field_date_value = build_field_date_value(payload)
    years = sorted(set(dk[:4] for dk in by_field_date_value["temp_c"].keys()))

    results = {field: {} for field in fields}

    for sigma in sigma_values:
        errors = {f: [] for f in fields}
        for held_out_year in years:
            ga_clim = build_gaussian_climatology_from_subset(by_field_date_value, held_out_year, sigma=sigma)
            for field in fields:
                for date_key, actual in by_field_date_value[field].items():
                    if date_key[:4] != held_out_year:
                        continue
                    doy = _doy_365(date_key)
                    errors[field].append(abs(ga_clim[doy - 1][field] - actual))
        for field in fields:
            results[field][sigma] = sum(errors[field]) / len(errors[field])

    # Also compute the existing moving-average MAE for reference, same folds
    ma_errors = {f: [] for f in fields}
    for held_out_year in years:
        ma_clim = build_moving_average_from_subset(by_field_date_value, held_out_year)
        for field in fields:
            for date_key, actual in by_field_date_value[field].items():
                if date_key[:4] != held_out_year:
                    continue
                doy = _doy_365(date_key)
                ma_errors[field].append(abs(ma_clim[doy - 1][field] - actual))
    ma_mae = {f: sum(ma_errors[f]) / len(ma_errors[f]) for f in fields}

    print(f"{'Field':<15}{'MA (ref)':>10}" + "".join(f"{'σ='+str(s):>9}" for s in sigma_values))
    for field in fields:
        best_sigma = min(results[field], key=results[field].get)
        row = f"{field:<15}{ma_mae[field]:>10.4f}"
        for s in sigma_values:
            marker = "*" if s == best_sigma else " "
            row += f"{results[field][s]:>8.4f}{marker}"
        print(row)
    print("\n  (* = best sigma for that field; MA (ref) = existing moving-average MAE, same folds)")

    return results, ma_mae


if __name__ == "__main__":
    compare(24.71, 46.68, "Riyadh")
    compare(18.22, 42.51, "Abha")

    KNOWN_LOCATIONS = {
        "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "dammam": (26.43, 50.10),
        "najran": (17.49, 44.13), "jazan": (16.89, 42.55), "abha": (18.22, 42.51),
        "tabuk": (28.38, 36.57), "qassim": (26.33, 43.98), "madinah": (24.47, 39.61),
        "makkah": (21.39, 39.86), "hail": (27.52, 41.69),
    }
    compare_all_cities(KNOWN_LOCATIONS)

    sweep_harmonics(24.71, 46.68, "Riyadh",
                    fields_to_test=["temp_c", "wind_speed_ms", "dewpoint_c", "precip_mm_day"])

    cross_validate(24.71, 46.68, "Riyadh")
    cross_validate_all_cities(KNOWN_LOCATIONS)

    sweep_gaussian_sigma(24.71, 46.68, "Riyadh")
    sweep_gaussian_sigma(18.22, 42.51, "Abha")