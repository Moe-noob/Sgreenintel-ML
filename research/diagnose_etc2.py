import sys
sys.path.insert(0, 'heatmap')
sys.path.insert(0, 'care')
from nasa_power import fetch_daily_climatology_full
from tracker import date_to_doy, fetch_open_meteo_forecast
from evapotranspiration import (
    saturation_vapor_pressure, slope_vapor_pressure_curve, psychrometric_constant,
    extraterrestrial_radiation, net_radiation, penman_monteith_et0_doy,
)
import datetime

lat, lon = 24.71, 46.68
clim, elevation_m, _ = fetch_daily_climatology_full(lat, lon)
doy = date_to_doy(datetime.date(2026, 9, 24))
c = clim[doy - 1]

forecast = fetch_open_meteo_forecast(lat, lon)
today = forecast[0]


def breakdown(label, temp_mean, temp_max, temp_min, dewpoint, wind, solar):
    delta = slope_vapor_pressure_curve(temp_mean)
    gamma = psychrometric_constant(elevation_m)
    es = (saturation_vapor_pressure(temp_max) + saturation_vapor_pressure(temp_min)) / 2
    ea = saturation_vapor_pressure(dewpoint)
    ra = extraterrestrial_radiation(lat, doy)
    rn = net_radiation(temp_max, temp_min, solar, ea, ra, elevation_m)

    aero_term = gamma * (900 / (temp_mean + 273)) * wind * (es - ea)
    rad_term = 0.408 * delta * rn
    et0 = penman_monteith_et0_doy(temp_mean, temp_max, temp_min, dewpoint, wind, solar,
                                  elevation_m, lat, doy)

    print(f"{label}:")
    print(f"  Rn (net radiation)      = {rn:.2f} MJ/m2/day")
    print(f"  radiation term (numer.) = {rad_term:.2f}")
    print(f"  aerodynamic term        = {aero_term:.2f}")
    print(f"  es-ea (vapor deficit)   = {es - ea:.2f} kPa")
    print(f"  ET0                     = {et0:.2f} mm/day\n")


breakdown("CLIMATOLOGICAL (baseline)", c["temp_c"], c["temp_max_c"], c["temp_min_c"],
          c["dewpoint_c"], c["wind_speed_ms"], c["solar_radiation_mj"])

breakdown("LIVE FORECAST", today["tmean"], today["tmax"], today["tmin"],
          today["dewpoint_c"], today["wind_speed_ms"], today["solar_radiation_mj"])