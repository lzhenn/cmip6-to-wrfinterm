"""Generic soil-layer remapping from CMIP6 native depths to WRF's 4 layers.

WRF's intermediate format expects exactly four soil layers, labeled by their
depth range in cm: ST/SM 000010, 010040, 040100, 100200 (i.e. 0-10, 10-40,
40-100, 100-200 cm). CMIP6 land models publish soil profiles on widely
different vertical meshes — CESM2 uses 25 layers spanning 1 cm to 42 m,
while MPI / EC-Earth3 publish only a single near-surface layer (`mrsos`,
`tslsi`).

The recommended remap algorithm:

  For each WRF target layer [lo, hi] (m):
    if the source provides `depth_bnds` (CMIP6 convention via the depth coord's
    `bounds` attribute):
       overlap_i = max(0, min(hi, d_hi_i) - max(lo, d_lo_i))   for each source layer
       result    = sum_i (overlap_i * source_value_i) / sum_i overlap_i
    else (no bounds):
       fall back to picking the source layer whose center is closest to (lo+hi)/2

When the source has no depth dimension at all (single-layer surface data
like MPI's mrsos), this module is not the right tool — the calling code
should either replicate the layer (legacy `2d-soilr` behavior) or skip the
soil records and let WRF compute via `surface_input_source=2`.
"""
import re

import numpy as np
import xarray as xr


# WRF's canonical soil layer ranges (cm). The label parser reverse-engineers
# these from the aim_v strings, but the list is here as documentation.
WRF_SOIL_LAYERS = [
    (0,   10,  '000010'),
    (10,  40,  '010040'),
    (40,  100, '040100'),
    (100, 200, '100200'),
]


_SOIL_LABEL_RE = re.compile(r'^(?:ST|SM)(\d{3})(\d{3})$')


def parse_wrf_soil_label(label):
    '''Parse a WRF aim_v label like `ST000010` or `SM010040`.

    Returns a (lo_cm, hi_cm) tuple. Raises ValueError on unrecognized input.
    '''
    m = _SOIL_LABEL_RE.match(label)
    if not m:
        raise ValueError(
            f"Unrecognized WRF soil label {label!r}; expected ST/SM + 6 digits "
            f"(e.g. ST000010, SM100200)")
    return int(m.group(1)), int(m.group(2))


def remap_soil_layer(da, depth_dim, lo_cm, hi_cm, depth_bnds=None):
    '''Reduce `da` along `depth_dim` to a single layer covering [lo_cm, hi_cm].

    Parameters
    ----------
    da : xr.DataArray
        Source field with a depth-like axis (and arbitrary other dims).
    depth_dim : str
        Name of the depth dimension on `da`.
    lo_cm, hi_cm : int
        Target layer range in centimetres (WRF convention).
    depth_bnds : np.ndarray or None, shape (n, 2)
        Layer boundaries in metres, if the source provides them. When given,
        we compute an overlap-weighted average across all source layers that
        intersect [lo_cm, hi_cm]. When None, fall back to nearest-center.

    Returns
    -------
    xr.DataArray
        Same shape as `da` minus `depth_dim`.

    Notes
    -----
    - If the WRF target layer falls entirely below the deepest source layer
      (e.g. ECMWF data ending at 2.89 m but the user wants 100-200 cm — fine,
      but if the deepest is at 0.5 m we'd get zero overlap), the function
      falls back to the deepest available source layer rather than returning
      NaN. This keeps real.exe happy at the cost of physical realism.
    '''
    lo_m, hi_m = lo_cm / 100.0, hi_cm / 100.0

    if depth_bnds is not None:
        bnds = np.asarray(depth_bnds, dtype=np.float64)
        # Tolerate reversed bounds order in some files.
        d_lo = np.minimum(bnds[:, 0], bnds[:, 1])
        d_hi = np.maximum(bnds[:, 0], bnds[:, 1])
        overlap = np.maximum(0.0, np.minimum(hi_m, d_hi) - np.maximum(lo_m, d_lo))
        total = overlap.sum()
        if total > 0:
            weights = overlap / total
            w_da = xr.DataArray(weights.astype(np.float64), dims=[depth_dim])
            return (da * w_da).sum(dim=depth_dim)
        # Zero overlap → target layer is outside source coverage.
        # Use the source layer whose midpoint is closest.

    # Fallback: nearest-center on the depth coord
    depth_vals = np.asarray(da.coords[depth_dim].values, dtype=np.float64)
    mid_m = 0.5 * (lo_m + hi_m)
    idx = int(np.argmin(np.abs(depth_vals - mid_m)))
    return da.isel({depth_dim: idx})


def read_depth_bnds(ds, depth_dim):
    '''Best-effort extraction of `depth_bnds` from a CMIP6 dataset.

    Looks at the depth coord's `bounds` attribute (CF convention). Returns
    None if the file doesn't provide bounds, in which case `remap_soil_layer`
    will fall back to nearest-center selection.
    '''
    if depth_dim not in ds:
        return None
    bnds_name = ds[depth_dim].attrs.get('bounds', '')
    if not bnds_name or bnds_name not in ds:
        return None
    return np.asarray(ds[bnds_name].values, dtype=np.float64)
