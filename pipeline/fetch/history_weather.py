"""One-off download of ERA5 weather history (Open-Meteo archive) for the Tasmanian areas.

Design (see docs/data_sources.md, Open-Meteo):
  - model: ERA5 (`models=era5`, 0.25 deg), one consistent reanalysis for every year
  - wind, radiation, air temperature from the nearest SEA cell (`cell_selection=sea`):
    over-water wind drives mixing/upwelling; land cells have land roughness
  - precipitation from the nearest LAND cell (`cell_selection=land`): the catchment draining
    into the estuary
  - each area's actual cells are resolved first with tiny 1-day requests, then the full
    history is downloaded once per DISTINCT cell
  - rate limits (open-meteo.com/en/pricing): >2 weeks of data for one location counts as
    multiple calls (fractional: days/14 per <=10 variables). Free tier: 5,000 calls/hour,
    10,000/day. We pace to <= HOURLY_BUDGET call-units per hour and stop at DAILY_BUDGET;
    re-running resumes (existing files are skipped).

Run:  uv run python -m pipeline.fetch.history_weather
"""

import csv
import json
import math
import time

from pipeline.config import RAW_DIR
from pipeline.features.areas import load_tas_areas
from pipeline.http import get

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OUT_DIR = RAW_DIR / "open_meteo" / "history_era5"
START, END = "2016-01-01", "2026-11-10"  # ERA5 is ~5 days behind real time
VARIABLES = {
    "sea": ["wind_speed_10m", "wind_direction_10m", "shortwave_radiation", "temperature_2m"],
    "land": ["precipitation"],
}
HOURLY_BUDGET = 4000.0  # stay well under the 5,000/hour limit
DAILY_BUDGET = 9000.0  # stay under the 10,000/day limit


def call_units(days: int, n_vars: int) -> float:
    """Open-Meteo's fractional call count: (days / 14) x (variables / 10), each at least 1."""
    return max(1.0, days / 14) * max(1.0, n_vars / 10)


def request(lat: float, lon: float, selection: str, start: str, end: str) -> dict:
    """One archive request for a point, returning the parsed JSON."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(VARIABLES[selection]),
        "models": "era5",
        "cell_selection": selection,
        "wind_speed_unit": "ms",
        "timezone": "UTC",
    }
    return get(ARCHIVE_URL, params=params).json()


def resolve_cells() -> list[dict]:
    """Map every area to its ERA5 sea and land cells (tiny 1-day requests, cached)."""
    path = OUT_DIR / "area_cells.csv"
    if path.exists():
        with path.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    areas = load_tas_areas()
    cent = areas.to_crs(28355).centroid.to_crs(4326)
    rows = []
    for area_id, pt in zip(areas.area_id, cent, strict=True):
        row = {"area_id": area_id, "centroid_lat": round(pt.y, 4), "centroid_lon": round(pt.x, 4)}
        for sel in ("sea", "land"):
            r = request(pt.y, pt.x, sel, START, START)
            row[f"{sel}_lat"], row[f"{sel}_lon"] = r["latitude"], r["longitude"]
            time.sleep(1)
        rows.append(row)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return rows


def main() -> None:
    """Resolve cells, then download each distinct cell's history with rate-limit pacing."""
    rows = resolve_cells()
    cells = sorted(
        {(sel, float(r[f"{sel}_lat"]), float(r[f"{sel}_lon"])) for r in rows for sel in VARIABLES}
    )
    print(f"{len(rows)} areas -> {len(cells)} distinct cells", flush=True)
    days = (time.mktime(time.strptime(END, "%Y-%m-%d")) - time.mktime(
        time.strptime(START, "%Y-%m-%d"))) / 86400 + 1  # fmt: skip
    spent = 0.0
    for sel, lat, lon in cells:
        out = OUT_DIR / f"{sel}_{lat}_{lon}.json"
        if out.exists():
            continue
        units = call_units(math.ceil(days), len(VARIABLES[sel]))
        if spent + units > DAILY_BUDGET:
            print("Daily budget reached; re-run tomorrow to resume.", flush=True)
            return
        out.write_text(json.dumps(request(lat, lon, sel, START, END)))
        spent += units
        print(f"ok {out.name} ({units:.0f} call-units, {spent:.0f} today)", flush=True)
        time.sleep(units / HOURLY_BUDGET * 3600)  # pace to the hourly budget


if __name__ == "__main__":
    main()
