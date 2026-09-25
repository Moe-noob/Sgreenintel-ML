import sys
sys.path.insert(0, 'heatmap')
sys.path.insert(0, 'care')
from nasa_power import fetch_daily_climatology_full
from tracker import date_to_doy, fetch_open_meteo_forecast
import datetime

lat, lon = 24.71, 46.68
clim, elevation_m, _ = fetch_daily_climatology_full(lat, lon)

doy = date_to_doy(datetime.date(2026, 9, 24))
c = clim[doy - 1]
print('CLIMATOLOGICAL (Sep 24 normal):')
print(f"  temp_mean={c['temp_c']:.1f}  temp_max={c['temp_max_c']:.1f}  temp_min={c['temp_min_c']:.1f}")
print(f"  dewpoint={c['dewpoint_c']:.1f}  wind={c['wind_speed_ms']:.2f} m/s  solar={c['solar_radiation_mj']:.2f} MJ")

forecast = fetch_open_meteo_forecast(lat, lon)
today = forecast[0]
print("\nLIVE FORECAST (Sep 24 actual):")
print(f"  temp_mean={today['tmean']:.1f}  temp_max={today['tmax']:.1f}  temp_min={today['tmin']:.1f}")
print(f"  dewpoint={today['dewpoint_c']:.1f}  wind={today['wind_speed_ms']:.2f} m/s  solar={today['solar_radiation_mj']:.2f} MJ")
