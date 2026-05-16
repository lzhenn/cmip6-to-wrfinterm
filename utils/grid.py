"""Output grid spec for the WRF intermediate writer.

Encapsulates lat/lon mesh, pressure levels, and soil-layer labels so that
different host models can target different resolutions without code edits.
Defaults reproduce the historical hard-coded grid (1deg global, 14 plev,
4 soil layers).
"""
import numpy as np


_DEFAULT_PLEV_HPA = [
    1000.0, 925.0, 850.0, 700.0, 600.0, 500.0, 400.0,
    300.0, 250.0, 200.0, 150.0, 100.0, 70.0, 50.0,
]
_DEFAULT_SOIL_LAYERS = ['000010', '010040', '040100', '100200']


class OutputGrid:
    """Target grid for ETL output.

    Defaults: 1deg global (181 x 360, SW corner -90/0), 14 standard pressure
    levels (Pa), and the 4 WRF soil-layer labels. Override any subset via
    constructor kwargs or `OutputGrid.from_config(cfg['OUTPUT'])`.
    """

    def __init__(self,
                 lat_start=-90.0, lat_end=90.0, nlat=181,
                 lon_start=0.0, lon_end=359.0, nlon=360,
                 plev_hpa=None,
                 soil_layers=None,
                 earth_rad=6371.229):
        self.nlat = int(nlat)
        self.nlon = int(nlon)
        self.lat_start = float(lat_start)
        self.lat_end = float(lat_end)
        self.lon_start = float(lon_start)
        self.lon_end = float(lon_end)
        self.lats = np.linspace(self.lat_start, self.lat_end, self.nlat)
        self.lons = np.linspace(self.lon_start, self.lon_end, self.nlon)
        self.deltlat = (self.lat_end - self.lat_start) / (self.nlat - 1) if self.nlat > 1 else 1.0
        self.deltlon = (self.lon_end - self.lon_start) / (self.nlon - 1) if self.nlon > 1 else 1.0
        plev_hpa = plev_hpa if plev_hpa is not None else _DEFAULT_PLEV_HPA
        self.plev = 100.0 * np.asarray(plev_hpa, dtype=np.float64)  # → Pa
        self.soil_layers = list(soil_layers) if soil_layers is not None else list(_DEFAULT_SOIL_LAYERS)
        self.earth_rad = float(earth_rad)

    @classmethod
    def from_config(cls, out_cfg):
        """Build a grid from a configparser [OUTPUT] section. Any key absent
        falls back to the class default, so existing configs continue to work
        without modification.

        Recognised optional keys:
          lat_start, lat_end, nlat
          lon_start, lon_end, nlon
          plev_hpa     -- comma-separated hPa values, e.g. "1000,925,850,..."
          soil_layers  -- comma-separated 6-char zero-padded labels, e.g. "000010,010040,..."
          earth_rad    -- Earth radius in km
        """
        if out_cfg is None:
            return cls()

        def _get(name, cast):
            if name in out_cfg:
                return cast(out_cfg[name])
            return None

        kw = {}
        for name, cast in (
                ('lat_start', float), ('lat_end', float), ('nlat', int),
                ('lon_start', float), ('lon_end', float), ('nlon', int),
                ('earth_rad', float)):
            v = _get(name, cast)
            if v is not None:
                kw[name] = v
        if 'plev_hpa' in out_cfg:
            kw['plev_hpa'] = [float(x) for x in out_cfg['plev_hpa'].split(',')]
        if 'soil_layers' in out_cfg:
            kw['soil_layers'] = [s.strip() for s in out_cfg['soil_layers'].split(',')]
        return cls(**kw)

    def __repr__(self):
        return (f"OutputGrid(nlat={self.nlat}, nlon={self.nlon}, "
                f"lat={self.lat_start}..{self.lat_end}, "
                f"lon={self.lon_start}..{self.lon_end}, "
                f"plev={len(self.plev)} levels, "
                f"soil={self.soil_layers})")
