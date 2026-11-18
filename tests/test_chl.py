"""Cloud-edge erosion in the per-area chl extraction."""

import numpy as np

from pipeline.features.chl import area_daily_stats, cloud_edge


def test_cloud_edge_marks_neighbours_of_gaps_but_not_of_land() -> None:
    valid = np.ones((1, 5, 5), dtype=bool)
    valid[0, 2, 2] = False  # a cloud gap in the middle
    land = np.zeros((5, 5), dtype=bool)
    land[:, 0] = True  # a land column on the left
    valid[0, :, 0] = False  # land pixels are never valid
    edge = cloud_edge(valid, land)
    expected = np.zeros((5, 5), dtype=bool)
    expected[1:4, 1:4] = True  # the 8 neighbours of the gap ...
    expected[2, 2] = False  # ... but not the gap itself
    assert (edge[0] == expected).all()  # pixels next to land (column 1, rows 0 and 4) not marked


def test_core_median_excludes_edge_pixels() -> None:
    chl = np.array([[[1.0, 1.0, 9.0]]])  # one day, three pixels
    mask = np.ones((1, 3), dtype=bool)
    edge = np.array([[[False, False, True]]])
    s = area_daily_stats(chl, mask, edge).iloc[0]
    assert s["n_valid"] == 3 and s["chl"] == 1.0
    assert s["n_core"] == 2 and s["chl_core"] == 1.0
