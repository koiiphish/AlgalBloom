"""Show progress and estimated time-to-finish of long-running background downloads.

It only READS the files those jobs write as they go (it never touches the jobs).

Run once:          uv run python -m pipeline.progress
Refresh every 30s: uv run python -m pipeline.progress --watch      (Ctrl+C to stop)
"""

import argparse
import csv
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from pipeline.config import RAW_DIR


@dataclass
class Status:
    """Progress of one job."""

    name: str
    done: int
    total: int
    started: float | None  # epoch seconds, or None if not started
    note: str = ""

    def line(self) -> str:
        """One formatted progress line with a bar, percentage and ETA."""
        if self.total == 0 or self.started is None:
            return f"{self.name:<34} not started {self.note}"
        frac = min(self.done / self.total, 1.0)
        bar = "#" * int(frac * 30) + "-" * (30 - int(frac * 30))
        if self.done >= self.total:
            eta = "done"
        elif self.done == 0:
            eta = "ETA: unknown (no progress yet)"
        else:
            elapsed = time.time() - self.started
            remaining = elapsed / self.done * (self.total - self.done)
            finish = datetime.now() + timedelta(seconds=remaining)
            eta = f"ETA {_fmt(remaining)} (about {finish:%H:%M})"
        return f"{self.name:<34} [{bar}] {self.done}/{self.total} {frac:6.1%}  {eta} {self.note}"


def _fmt(seconds: float) -> str:
    """Human-readable duration, e.g. '1h 05m' or '7m 30s'."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


def _created(path: Path) -> float | None:
    """File creation time (Windows) / earliest available time, or None if missing."""
    return os.stat(path).st_ctime if path.exists() else None


def weather_status() -> Status:
    """ERA5 weather download: one JSON file per distinct grid cell."""
    d = RAW_DIR / "open_meteo" / "history_era5"
    cells_file = d / "area_cells.csv"
    if not cells_file.exists():
        return Status("ERA5 weather (Open-Meteo)", 0, 0, None)
    with cells_file.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cells = {(s, r[f"{s}_lat"], r[f"{s}_lon"]) for r in rows for s in ("sea", "land")}
    files = list(d.glob("sea_*.json")) + list(d.glob("land_*.json"))
    return Status("ERA5 weather (Open-Meteo)", len(files), len(cells), _created(cells_file),
                  "(paced ~4 min per cell to respect rate limits)")  # fmt: skip


def mai_status() -> list[Status]:
    """Maria Island independent satellite chl: one CSV row per sensor-day."""
    from pipeline.fetch.recon_mai_independent import OUT, SENSORS

    counts: dict[str, int] = {}
    if OUT.exists():
        with OUT.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                counts[r["sensor"]] = counts.get(r["sensor"], 0) + 1
    out = []
    start = _created(OUT)
    for sensor, (_, _, first, last, step) in SENSORS.items():
        total = ((last - first).days // step) + 1
        out.append(Status(f"Maria Island chl: {sensor}", counts.get(sensor, 0), total, start))
    # The second sensor only starts after the first finishes: base its ETA on overall rate.
    total_all = sum(s.total for s in out)
    done_all = sum(s.done for s in out)
    out.append(Status("Maria Island chl: overall", done_all, total_all, start))
    return out


def show() -> None:
    """Print the status of every tracked job."""
    print(f"Background jobs - {datetime.now():%Y-%m-%d %H:%M:%S}\n")
    for s in [weather_status(), *mai_status()]:
        print(s.line())
    print("\nLogs: data/raw/open_meteo/history_weather.log, data/interim/mai_independent.log")


def main() -> None:
    """Show once, or refresh every 30 s with --watch."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true", help="refresh every 30 seconds")
    args = parser.parse_args()
    if not args.watch:
        show()
        return
    try:
        while True:
            os.system("cls" if os.name == "nt" else "clear")  # noqa: S605 - clear the terminal
            show()
            time.sleep(30)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
