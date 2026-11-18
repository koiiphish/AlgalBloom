"""Weather features per area from ERA5 (Open-Meteo archive), aggregated to Hobart days.

Two kinds of features for issue date t:
  - recent (past) weather, using days <= t - WEATHER_LAG_DAYS: wind, radiation, rain sums
  - forecast-window drivers `fc7_*`, aggregated over t+1..t+7. In TRAINING these come from
    observed ERA5 (a "perfect forecast" emulation, a stated limitation, brief section 6);
    in operation and in the test-period evaluation they come from issued forecasts
    (Open-Meteo forecast / Previous Runs API, archived from 2024).

Wind is averaged as a vector (u, v), not by averaging directions. Direction is meteorological
("from"), so u = -speed*sin(dir), v = -speed*cos(dir): u > 0 blows toward the east, and
v > 0 toward the north (i.e. a southerly wind).

Run:  uv run python -m pipeline.features.weather
Output: data/interim/weather_area_day.parquet
"""

import json

import numpy as np
import pandas as pd

from pipeline.config import DATA_DIR, RAW_DIR
from pipeline.features.availability import WEATHER_LAG_DAYS
from pipeline.features.target import forward_window

WEATHER_DIR = RAW_DIR / "open_meteo" / "history_era5"
OUT_PATH = DATA_DIR / "interim" / "weather_area_day.parquet"
LOCAL_TZ = "Australia/Hobart"
RAIN_WINDOWS = (3, 7, 14, 30)


def wind_components(speed: pd.Series, direction_deg: pd.Series) -> tuple[pd.Series, pd.Series]:
    """(u, v) from speed and meteorological 'from' direction in degrees."""
    rad = np.deg2rad(direction_deg)
    return -speed * np.sin(rad), -speed * np.cos(rad)


def hourly_json_to_frame(payload: dict) -> pd.DataFrame:
    """Open-Meteo hourly JSON -> DataFrame indexed by UTC timestamp."""
    h = payload["hourly"]
    idx = pd.to_datetime(h["time"]).tz_localize("UTC")
    return pd.DataFrame({k: v for k, v in h.items() if k != "time"}, index=idx)


def sea_daily(hourly: pd.DataFrame) -> pd.DataFrame:
    """Daily (Hobart calendar day) wind, radiation and air temperature from sea-cell hours."""
    h = hourly.tz_convert(LOCAL_TZ)
    u, v = wind_components(h["wind_speed_10m"], h["wind_direction_10m"])
    day = h.index.normalize().tz_localize(None)
    df = pd.DataFrame(
        {
            "wind_u": u.to_numpy(),
            "wind_v": v.to_numpy(),
            "wind_speed": h["wind_speed_10m"].to_numpy(),
            "radiation_mj": h["shortwave_radiation"].clip(lower=0).to_numpy() * 3600 / 1e6,
            "air_temp": h["temperature_2m"].to_numpy(),
        },
        index=day,
    )
    g = df.groupby(level=0)
    return pd.DataFrame(
        {
            "wind_u": g["wind_u"].mean(),
            "wind_v": g["wind_v"].mean(),
            "wind_speed": g["wind_speed"].mean(),
            "wind_speed_max": g["wind_speed"].max(),
            "radiation_mj": g["radiation_mj"].sum(),
            "air_temp": g["air_temp"].mean(),
        }
    )


def land_daily(hourly: pd.DataFrame) -> pd.DataFrame:
    """Daily rainfall (mm, Hobart calendar day) from land-cell hours."""
    h = hourly.tz_convert(LOCAL_TZ)
    day = h.index.normalize().tz_localize(None)
    return h["precipitation"].groupby(day).sum().to_frame("rain_mm")


def area_weather_features(daily: pd.DataFrame, lag: int = WEATHER_LAG_DAYS) -> pd.DataFrame:
    """Past-weather and forecast-window features for one area (daily index, complete calendar)."""
    d = daily.asfreq("D")
    past = d.shift(lag)  # value at t = observation at t - lag
    out = pd.DataFrame(index=d.index)
    for col in ("wind_u", "wind_v", "wind_speed", "radiation_mj", "air_temp"):
        out[f"{col}_past3"] = past[col].rolling(3, min_periods=2).mean()
    for w in RAIN_WINDOWS:
        out[f"rain_past{w}"] = past["rain_mm"].rolling(w, min_periods=max(1, w // 2)).sum()
    # Forecast window t+1..t+7 (observed in training; issued forecasts in operation/test).
    for col in ("wind_u", "wind_v", "wind_speed", "radiation_mj", "air_temp"):
        out[f"fc7_{col}"] = forward_window(d[col])[0]
    rain_mean, rain_n = forward_window(d["rain_mm"])
    out["fc7_rain_sum"] = rain_mean * rain_n
    return out


def build() -> pd.DataFrame:
    """Area x day weather features for all Tas areas (needs the downloaded ERA5 files)."""
    cells = pd.read_csv(WEATHER_DIR / "area_cells.csv")
    sea_cache: dict[str, pd.DataFrame] = {}
    land_cache: dict[str, pd.DataFrame] = {}
    parts = []
    for r in cells.itertuples():
        sea_key = f"sea_{r.sea_lat}_{r.sea_lon}.json"
        land_key = f"land_{r.land_lat}_{r.land_lon}.json"
        if sea_key not in sea_cache:
            sea_cache[sea_key] = sea_daily(
                hourly_json_to_frame(json.loads((WEATHER_DIR / sea_key).read_text()))
            )
        if land_key not in land_cache:
            land_cache[land_key] = land_daily(
                hourly_json_to_frame(json.loads((WEATHER_DIR / land_key).read_text()))
            )
        daily = sea_cache[sea_key].join(land_cache[land_key], how="outer")
        f = area_weather_features(daily)
        f.insert(0, "area_id", r.area_id)
        parts.append(f)
    return pd.concat(parts).rename_axis("date").reset_index()


def main() -> None:
    """Build, save and summarise."""
    df = build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)
    print(f"wrote {len(df):,} rows -> {OUT_PATH}")
    print("missing share:", df.drop(columns=["area_id", "date"]).isna().mean().round(3).to_dict())


if __name__ == "__main__":
    main()
