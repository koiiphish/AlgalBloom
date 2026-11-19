"""Harvest areas as satellite-pixel lists, so the daily job never needs theLIST (D014 update).

On 2026-11-19 theLIST closed the connection when the GitHub runner asked for the boundaries.
The daily job only uses the boundaries to choose which OLCI pixels belong to each area, so we
store exactly that instead: for every area, the global OLCI grid indices of the pixels whose
centre lies inside the 2 km-buffered polygon (the same rule as training, pipeline.features.chl),
plus its name, status-matching key and published point, and the download boxes.

The OLCI 1/180 deg grid is global and shared by the NRT and multi-year products (checked
2026-11-19): pixel centres are at lat = -90 + (k + 0.5) / 180 and lon = -180 + (k + 0.5) / 180.

Storage: gzip + base64 JSON in the GitHub secret TAS_AREA_PIXELS (decision by Timothy,
2026-11-19). It is a secret because it derives from theLIST polygons, whose licence is not
yet confirmed; nothing here is committed. Locally the same text can sit in the git-ignored
data/ folder.

Build locally (needs the polygons and the history files in data/):
    uv run python -m pipeline.forecast.area_pixels --export
then paste the text file's contents into the secret.
"""

import argparse
import base64
import glob
import gzip
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from pipeline.config import RAW_DIR, BBox

SECRET_ENV = "TAS_AREA_PIXELS"
LOCAL_PATH = RAW_DIR / "thelist" / "tas_area_pixels.txt"  # git-ignored copy of the secret
RES = 180  # pixels per degree
SECRET_LIMIT_BYTES = 48 * 1024  # GitHub Actions secret size limit


def lat_index(lat: np.ndarray) -> np.ndarray:
    """Global OLCI row index of latitudes (pixel centres)."""
    return np.rint((np.asarray(lat, dtype=float) + 90) * RES - 0.5).astype(np.int64)


def lon_index(lon: np.ndarray) -> np.ndarray:
    """Global OLCI column index of longitudes (pixel centres)."""
    return np.rint((np.asarray(lon, dtype=float) + 180) * RES - 0.5).astype(np.int64)


@dataclass(frozen=True)
class AreaSet:
    """Everything the daily job needs to know about the areas."""

    meta: pd.DataFrame  # area_id, harvest_area, growing_area, match_key, lon, lat
    pixels: dict[str, tuple[np.ndarray, np.ndarray]]  # area_id -> (row index, column index)
    boxes: list[BBox]

    @property
    def area_ids(self) -> list[str]:
        """Area IDs in a stable order."""
        return self.meta["area_id"].tolist()

    def pixel_centres(self, area_id: str) -> tuple[np.ndarray, np.ndarray]:
        """(lat, lon) of an area's pixel centres."""
        ky, kx = self.pixels[area_id]
        return -90 + (ky + 0.5) / RES, -180 + (kx + 0.5) / RES


def encode(obj: dict) -> str:
    """Compact JSON -> gzip -> base64 text (fits in a secret)."""
    raw = json.dumps(obj, separators=(",", ":")).encode()
    return base64.b64encode(gzip.compress(raw, compresslevel=9)).decode("ascii")


def decode(text: str) -> dict:
    """Inverse of encode."""
    return json.loads(gzip.decompress(base64.b64decode(text.strip())))


def from_dict(d: dict) -> AreaSet:
    """Build an AreaSet from the decoded secret. Pixel indices are stored as offsets from
    each area's first row/column to keep the text small."""
    keys = ("area_id", "harvest_area", "growing_area", "match_key", "lon", "lat")
    meta = pd.DataFrame([{k: a[k] for k in keys} for a in d["areas"]])
    pixels = {
        a["area_id"]: (a["ky0"] + np.asarray(a["dy"], dtype=np.int64),
                       a["kx0"] + np.asarray(a["dx"], dtype=np.int64))
        for a in d["areas"]
    }  # fmt: skip
    boxes = [BBox(**b) for b in d["boxes"]]
    return AreaSet(meta=meta, pixels=pixels, boxes=boxes)


def load() -> AreaSet:
    """From the TAS_AREA_PIXELS secret (GitHub Actions) or the local git-ignored copy."""
    local = LOCAL_PATH.read_text() if LOCAL_PATH.exists() else ""
    text = os.environ.get(SECRET_ENV) or local
    if not text.strip():
        raise FileNotFoundError(
            f"no area pixels: set the {SECRET_ENV} secret, or run "
            "`python -m pipeline.forecast.area_pixels --export` locally"
        )
    return from_dict(decode(text))


def mask_for(area: AreaSet, area_id: str, lat: np.ndarray, lon: np.ndarray) -> np.ndarray | None:
    """(lat, lon) boolean mask of an area's pixels on a file's grid; None unless every pixel of
    the area is inside the file (the training extraction also used only fully covered areas)."""
    ky, kx = area.pixels[area_id]
    rows = {k: i for i, k in enumerate(lat_index(lat))}
    cols = {k: j for j, k in enumerate(lon_index(lon))}
    if not (all(k in rows for k in ky) and all(k in cols for k in kx)):
        return None
    mask = np.zeros((lat.size, lon.size), dtype=bool)
    mask[[rows[k] for k in ky], [cols[k] for k in kx]] = True
    return mask


def extract(path: Path, area: AreaSet) -> pd.DataFrame:
    """Daily stats per area from one OLCI file: pipeline.features.chl.extract_file, but with
    the stored pixel lists instead of polygons (same cloud-edge rule, same statistics)."""
    from pipeline.features.chl import area_daily_stats, cloud_edge

    with xr.open_dataset(path) as ds:
        lat, lon = ds.latitude.values, ds.longitude.values
        chl = ds.CHL.values
        land = (ds.flags.values == 1).any(axis=0)
        dates = pd.to_datetime(ds.time.values).normalize()
    edge = cloud_edge(np.isfinite(chl) & (chl > 0), land)
    parts = []
    for area_id in area.area_ids:
        mask = mask_for(area, area_id, lat, lon)
        if mask is None:
            continue
        stats = area_daily_stats(chl, mask, edge)
        stats.insert(0, "date", dates)
        stats.insert(0, "area_id", area_id)
        parts.append(stats)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def footprints(area: AreaSet):
    """Each area's pixel centres as a MultiPoint (EPSG:4326), for distance-based lookups such
    as the nearest SST grid cells."""
    import geopandas as gpd
    import shapely

    geoms = [
        shapely.MultiPoint(np.column_stack(area.pixel_centres(a)[::-1])) for a in area.area_ids
    ]
    return gpd.GeoDataFrame({"area_id": area.area_ids}, geometry=geoms, crs=4326)


def build(history_glob: str | None = None) -> dict:
    """Pixel lists from the local polygons on the real OLCI grid (the training rule)."""
    from pipeline.features.areas import buffer_areas, load_tas_areas
    from pipeline.features.chl import HISTORY_DIR, pixel_mask
    from pipeline.fetch.history_olci_300m import tas_boxes
    from pipeline.publish.site import area_points

    areas = load_tas_areas()
    buffered = buffer_areas(areas)
    files = sorted(glob.glob(history_glob or str(HISTORY_DIR / "tas_*_2024.nc")))
    found: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for f in files:
        with xr.open_dataset(f) as ds:
            lat, lon = ds.latitude.values, ds.longitude.values
        for row in buffered.itertuples():
            if row.area_id in found:
                continue
            m = pixel_mask(lat, lon, row.geometry)
            iy, ix = np.nonzero(m)
            ky, kx = lat_index(lat[iy]), lon_index(lon[ix])
            # Same inclusion rule as training: the buffered polygon must fit inside the box.
            west, south, east, north = row.geometry.bounds
            inside = lat.min() <= south and north <= lat.max() and lon.min() <= west <= east
            if m.any() and inside and east <= lon.max():
                found[row.area_id] = (ky, kx)
    missing = set(areas.area_id) - set(found)
    if missing:
        raise ValueError(f"areas without pixels: {sorted(missing)}")
    pts = area_points(areas).set_index("area_id")
    out_areas = []
    for aid in sorted(found):
        ky, kx = found[aid]
        p = pts.loc[aid]
        out_areas.append({
            "area_id": aid, "harvest_area": p.harvest_area, "growing_area": p.growing_area,
            "match_key": p.match_key, "lon": float(p.lon), "lat": float(p.lat),
            "ky0": int(ky.min()), "kx0": int(kx.min()),
            "dy": (ky - ky.min()).tolist(), "dx": (kx - kx.min()).tolist(),
        })  # fmt: skip
    return {
        "version": 1,
        "grid": "OLCI 1/180 deg global; centre = -90/-180 + (k + 0.5) / 180",
        "buffer_km": float(buffered["buffer_km"].iloc[0]),
        "boxes": [b.__dict__ for b in tas_boxes()],
        "areas": out_areas,
    }


def main() -> None:
    """Build, check against the training pixel counts, and write the secret text locally."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", action="store_true", help=f"write {LOCAL_PATH}")
    args = parser.parse_args()
    d = build()
    text = encode(d)
    n = {a["area_id"]: len(a["dy"]) for a in d["areas"]}
    from pipeline.features.chl import OUT_PATH

    trained = pd.read_parquet(OUT_PATH).groupby("area_id")["n_pixels"].first()
    diff = {a: (n[a], int(trained[a])) for a in n if n[a] != trained.get(a)}
    print(f"{len(n)} areas, {sum(n.values())} pixels; text {len(text):,} bytes "
          f"(secret limit {SECRET_LIMIT_BYTES:,})")  # fmt: skip
    print("pixel counts identical to training:" if not diff else "DIFFERENT from training:",
          diff or "yes")  # fmt: skip
    if len(text) > SECRET_LIMIT_BYTES:
        raise SystemExit("too large for a GitHub secret")
    if args.export:
        Path(LOCAL_PATH).write_text(text, encoding="ascii")
        print(f"wrote {LOCAL_PATH} (git-ignored). Paste its contents into the {SECRET_ENV} secret.")


if __name__ == "__main__":
    main()
