"""Phase 0 recon: pull one week of weather (archive + forecast) and marine data from
Open-Meteo for one SA and one Tasmanian test point.

Run:  uv run python -m pipeline.fetch.recon_open_meteo

Terms (read 2026-11-17, https://open-meteo.com/en/terms): free API is non-commercial only;
a free website with no ads/subscriptions qualifies. Limits: <10,000 calls/day, 5,000/hour,
600/minute. Data licence CC BY 4.0 (https://open-meteo.com/en/licence).

Variable names are validated by the API itself: an unknown name returns HTTP 400 with a
reason, which `get()` raises, so nothing here is silently wrong.
"""

import json
import time

from pipeline.config import RAW_DIR, RECON_END, RECON_START, TEST_POINTS
from pipeline.http import get

PAUSE_S = 1.0

HOURLY_WEATHER = [
    "temperature_2m",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "shortwave_radiation",
]
HOURLY_MARINE = ["wave_height", "sea_surface_temperature"]

# (name, endpoint, extra params). Archive = past observed/reanalysis; forecast = next 16 days.
ENDPOINTS = [
    (
        "archive",
        "https://archive-api.open-meteo.com/v1/archive",
        {
            "hourly": ",".join(HOURLY_WEATHER),
            "start_date": RECON_START.isoformat(),
            "end_date": RECON_END.isoformat(),
        },
    ),
    (
        "forecast",
        "https://api.open-meteo.com/v1/forecast",
        {"hourly": ",".join(HOURLY_WEATHER), "forecast_days": 16},
    ),
    (
        "marine_forecast",
        "https://marine-api.open-meteo.com/v1/marine",
        {"hourly": ",".join(HOURLY_MARINE), "forecast_days": 8},
    ),
]


def main() -> None:
    """Call each endpoint for each test point and save the raw JSON response."""
    out_dir = RAW_DIR / "open_meteo"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, url, extra in ENDPOINTS:
        for pt in TEST_POINTS:
            params = {"latitude": pt.lat, "longitude": pt.lon, "timezone": "UTC", **extra}
            data = get(url, params=params).json()
            out = out_dir / f"{name}_{pt.name}.json"
            out.write_text(json.dumps(data))
            times = data["hourly"]["time"]
            missing = {
                v: sum(x is None for x in vals) for v, vals in data["hourly"].items() if v != "time"
            }
            print(f"ok {name:16s} {pt.name:13s} {times[0]} -> {times[-1]}  nulls={missing}")
            time.sleep(PAUSE_S)


if __name__ == "__main__":
    main()
