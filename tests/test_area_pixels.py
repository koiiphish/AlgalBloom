"""Stored area pixel lists (the TAS_AREA_PIXELS secret): encoding, grid indices, masks."""

import numpy as np

from pipeline.forecast import area_pixels as A


def _grid(lat0: float, lon0: float, n: int) -> tuple[np.ndarray, np.ndarray]:
    """A patch of the global OLCI grid (pixel centres), stored as float32 like the files."""
    ky0, kx0 = A.lat_index(np.array([lat0]))[0], A.lon_index(np.array([lon0]))[0]
    lat = (-90 + (ky0 + np.arange(n) + 0.5) / A.RES).astype(np.float32)
    lon = (-180 + (kx0 + np.arange(n) + 0.5) / A.RES).astype(np.float32)
    return lat, lon


def _area_set() -> A.AreaSet:
    """One area of three pixels."""
    d = {"boxes": [{"name": "b", "west": 147.0, "south": -43.0, "east": 148.0, "north": -42.0}],
         "areas": [{"area_id": "tas:x:1", "harvest_area": "1", "growing_area": "X",
                    "match_key": "tas:x:1", "lon": 147.5, "lat": -42.5,
                    "ky0": int(A.lat_index(np.array([-42.5]))[0]),
                    "kx0": int(A.lon_index(np.array([147.5]))[0]),
                    "dy": [0, 0, 1], "dx": [0, 1, 1]}]}  # fmt: skip
    return A.from_dict(A.decode(A.encode(d)))


def test_grid_index_round_trip_survives_float32():
    """Pixel centres stored as float32 must map back to their integer grid index."""
    lat, lon = _grid(-42.5, 147.5, 50)
    assert np.all(np.diff(A.lat_index(lat)) == 1) and np.all(np.diff(A.lon_index(lon)) == 1)


def test_encode_decode_and_mask():
    """The mask marks exactly the stored pixels, wherever the file's patch starts."""
    area = _area_set()
    lat, lon = _grid(-42.52, 147.48, 20)
    mask = A.mask_for(area, "tas:x:1", lat, lon)
    assert mask is not None and mask.sum() == 3
    iy, ix = np.nonzero(mask)
    assert set(zip(A.lat_index(lat[iy]), A.lon_index(lon[ix]), strict=True)) == set(
        zip(*area.pixels["tas:x:1"], strict=True)
    )


def test_area_not_fully_in_file_is_skipped():
    """Like the training extraction, an area only partly covered by a file is not used."""
    area = _area_set()
    lat, lon = _grid(-42.5, 147.5, 1)  # contains the first pixel only
    assert A.mask_for(area, "tas:x:1", lat, lon) is None
