import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "heatmap")
import nasa_power as npw
import site_elevation as se
import aridity as ar

CSV = "data/external/saudi-hourly-weather-data_Historical.csv"
CASES = ["ABHA", "NEJRAN", "KING ABDULLAH BIN ABDULAZIZ"]   # last one is (I believe) Jazan's airport: check the lat/lon it prints (Jazan ~ 16.9 N, 42.6 E)
Y0, Y1 = 2016, 2018          # full years that both NASA and the stations cover (the stations stop in May 2019)
MIN_OBS = 6                  # a day needs this many readings to trust its max/min
CHECK_DEM = True             # also ask Open-Meteo for the map height at the station (needs internet)
HEAT_LIMITS = (35, 38, 40)   # count days per year with Tmax above these
MD = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

cols = ["STATION_ID", "STATION_NAME", "OBSERVATION_DATE", "LATITUDE", "LONGITUDE", "ELEVATION",
        "WIND_SPEED_RATE", "AIR_TEMPERATURE", "AIR_TEMPERATURE_DEW_POINT"]
df = pd.read_csv(CSV, usecols=cols)
df["t_utc"] = pd.to_datetime(df["OBSERVATION_DATE"], format="ISO8601")

def month_means(v):                                   # 365 daily values -> 12 monthly means
    out, j = [], 0
    for n in MD:
        out.append(float(np.nanmean(v[j:j + n]))); j += n
    return np.array(out)

for name in CASES:
    s = df[(df.STATION_NAME.str.strip() == name) & df.t_utc.dt.year.between(Y0, Y1)].copy()
    if s.empty:
        print(f"\n##### {name}: no rows in {Y0}-{Y1}"); continue
    for col, limit in (("AIR_TEMPERATURE", 99), ("AIR_TEMPERATURE_DEW_POINT", 99), ("WIND_SPEED_RATE", 90)):
        s.loc[s[col] >= limit, col] = np.nan                                   # missing-value codes
    s["wind_2m"] = s["WIND_SPEED_RATE"] * 4.87 / np.log(67.8 * 10 - 5.42)      # 10 m -> 2 m (FAO-56 Eq. 47)
    s["day"] = (s["t_utc"] + pd.Timedelta(hours=3)).dt.floor("D")              # local (UTC+3) day
    d = s.groupby("day").agg(n=("AIR_TEMPERATURE", "count"), tmax=("AIR_TEMPERATURE", "max"), tmin=("AIR_TEMPERATURE", "min"),
                             dew=("AIR_TEMPERATURE_DEW_POINT", "mean"), wind=("wind_2m", "mean"))
    d = d[d.n >= MIN_OBS]
    lat, lon, z_stn = round(float(s.LATITUDE.iloc[0]), 2), round(float(s.LONGITUDE.iloc[0]), 2), float(s.ELEVATION.iloc[0])
    print(f"\n{'#' * 78}\n##### {name}: lat {lat}, lon {lon}, station elevation {z_stn:.0f} m, {len(d)} usable days in {Y0}-{Y1}")

    clim, z_cell, raw_years = npw._fetch_uncorrected(lat, lon)                 # raw NASA cell values
    shift = se.lapse_shift_c(z_cell, z_stn)
    print(f"NASA cell elevation {z_cell:.0f} m -> station {z_stn:.0f} m: lapse shift {shift:+.2f} C")
    if CHECK_DEM:
        dem = se.fetch_site_elevation_m(lat, lon)
        print("map (DEM) height at these coordinates:", f"{dem:.0f} m" if dem is not None else "unavailable")

    # ---- day-by-day Tmax / Tmin: station vs NASA raw vs NASA corrected, same dates ----
    rows = []
    for day, r in d.iterrows():
        leap = day.year % 4 == 0 and (day.year % 100 != 0 or day.year % 400 == 0)
        if leap and day.month == 2 and day.day >= 28:
            continue                                                            # NASA cache folds 29 Feb into 28 Feb
        ry = raw_years.get(str(day.year))
        if not ry:
            continue
        i = npw._doy_365(day.strftime("%Y%m%d")) - 1
        nmax, nmin = ry["temp_max_c"][i], ry["temp_min_c"][i]
        if nmax is None or nmin is None:
            continue
        rows.append((day.month, r.tmax, r.tmin, nmax, nmin))
    m = pd.DataFrame(rows, columns=["month", "s_max", "s_min", "n_max", "n_min"])
    m["c_max"], m["c_min"] = m.n_max + shift, m.n_min + shift
    t = m.groupby("month").mean().round(1)
    t["err_raw_max"], t["err_corr_max"] = (t.n_max - t.s_max).round(1), (t.c_max - t.s_max).round(1)
    t["err_raw_min"], t["err_corr_min"] = (t.n_min - t.s_min).round(1), (t.c_min - t.s_min).round(1)
    print("\nMONTHLY MEAN (C). s_ = station, n_ = NASA raw, c_ = NASA corrected with the station's own height; err = NASA - station")
    print(t[["s_max", "n_max", "c_max", "err_raw_max", "err_corr_max", "s_min", "n_min", "c_min", "err_raw_min", "err_corr_min"]].to_string())
    for lab, sc, nc, cc in (("Tmax", "s_max", "n_max", "c_max"), ("Tmin", "s_min", "n_min", "c_min")):
        bias_raw, bias_cor = (m[nc] - m[sc]).mean(), (m[cc] - m[sc]).mean()
        mae_raw, mae_cor = (m[nc] - m[sc]).abs().mean(), (m[cc] - m[sc]).abs().mean()
        emp = f"{bias_raw / ((z_stn - z_cell) / 1000):.1f} C/km" if abs(z_stn - z_cell) > 100 else "n/a (small height gap)"
        print(f"{lab}: bias raw {bias_raw:+.2f} -> corrected {bias_cor:+.2f} C | mean abs error raw {mae_raw:.2f} -> corrected {mae_cor:.2f} C | lapse rate that would fit exactly: {emp} (code uses 6.5)")
    n_years = Y1 - Y0 + 1
    print("days per year with Tmax above a limit (station | NASA raw | NASA corrected):")
    for lim in HEAT_LIMITS:
        print(f"   > {lim} C: {(m.s_max > lim).sum() / n_years:6.1f} | {(m.n_max > lim).sum() / n_years:6.1f} | {(m.c_max > lim).sum() / n_years:6.1f}")

    # ---- dewpoint and wind: station vs the typical-year NASA climatology after the app's own corrections ----
    new_clim, _, info = se.correct_climatology(clim, raw_years, z_cell, z_stn)
    cond, ainfo = ar.condition_climatology(new_clim)
    sm = d.groupby(d.index.month).mean(numeric_only=True)
    tab = pd.DataFrame({"stn_dew": sm.dew.values,
                        "nasa_dew": month_means(np.array([c.get("dewpoint_raw_c", c["dewpoint_c"]) for c in cond])),
                        "nasa_dew_conditioned": month_means(np.array([c["dewpoint_c"] for c in cond])),
                        "stn_Tmin_minus_dew": (d.groupby(d.index.month).tmin.mean() - sm.dew).values,
                        "stn_wind_2m": sm.wind.values, "nasa_wind_2m": month_means(np.array([c["wind_speed_ms"] for c in cond]))},
                       index=range(1, 13)).round(1)
    if ainfo:
        print(f"\naridity: AI {ainfo['aridity_index']:.3f} ({ainfo['aridity_class']}) -> aT = {ainfo['aT_c']} C")
    print("DEWPOINT (C) and WIND at 2 m (m/s) by month. nasa_dew = after the elevation shift; conditioned = after the humidity fix")
    print(tab.to_string())