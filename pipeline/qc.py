"""Basic quality-control helpers shared by fetch, features and notebooks."""

import numpy as np
import xarray as xr


def mask_invalid_chl(chl: xr.DataArray) -> xr.DataArray:
    """Turn non-physical chlorophyll-a values into NaN.

    Why: some IMOS VIIRS daily files store missing pixels as -999 *without* declaring a
    _FillValue (seen in J.P1D.20261102...chl_oci.nc), while other days use NaN. Real
    chlorophyll is always > 0 mg/m^3, so anything <= 0 is treated as missing.
    """
    return chl.where(chl > 0)


def valid_fraction(da: xr.DataArray) -> float:
    """Fraction of cells that hold a finite value (0..1). Returns 0.0 for an empty array."""
    values = np.asarray(da.values)
    if values.size == 0:
        return 0.0
    return float(np.isfinite(values).mean())
