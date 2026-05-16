#!/usr/bin/env python3
"""
Generate minimal synthetic CESM2-format CMIP6 files for smoke-testing cmip6-to-wrfinterm.

Output: sample/CESM2/ (same dir as this script)
Files cover 1990-01-01 00:00 to 1990-01-02 00:00 (5 time steps at 6h).
Grid: 10x20 (lat x lon), 3 hybrid levels, 2 pressure levels, 4 soil layers.

Run:
    conda run -n uranus-cmip python3 sample/CESM2/gen_fake_data.py
"""

import os
import numpy as np
import netCDF4 as nc
import cftime

OUTDIR = os.path.dirname(os.path.abspath(__file__))
MEM = "r11i1p1f1"
GRID = "gn"
EXP = "historical"
MODEL = "CESM2"
VER = "v20190313"

# Small grid for fast testing
NLAT, NLON = 10, 20
NLEV = 3       # hybrid model levels
NPLEV = 2      # pressure levels (6hrPlevPt)
NSOIL = 4      # soil layers

LATS = np.linspace(-90, 90, NLAT, dtype=np.float32)
LONS = np.linspace(0, 355, NLON, dtype=np.float32)

# CESM2 hybrid coefficients (top 3 levels from real data, scaled)
AP = np.array([0.0, 500.0, 2000.0], dtype=np.float64)   # Pa
B  = np.array([0.0, 0.01,  0.05],   dtype=np.float64)
P0 = 100000.0  # Pa

# Time: 1990-01-01 00Z to 1990-01-02 00Z, 5 steps × 6h
TIMES_6H = [
    cftime.DatetimeNoLeap(1990, 1, 1,  0),
    cftime.DatetimeNoLeap(1990, 1, 1,  6),
    cftime.DatetimeNoLeap(1990, 1, 1, 12),
    cftime.DatetimeNoLeap(1990, 1, 1, 18),
    cftime.DatetimeNoLeap(1990, 1, 2,  0),
]
# Monthly soil: just January 1990
TIMES_MON = [cftime.DatetimeNoLeap(1990, 1, 16, 12)]
# Daily SST: 3 days around 1990-01-01
TIMES_DAY = [
    cftime.DatetimeNoLeap(1990, 1,  1),
    cftime.DatetimeNoLeap(1990, 1,  2),
    cftime.DatetimeNoLeap(1990, 1,  3),
]

PLEV_HPA = np.array([100000.0, 85000.0], dtype=np.float64)  # Pa for 6hrPlevPt
SOIL_DEPTHS = np.array([0.05, 0.25, 0.70, 1.50], dtype=np.float64)  # m


def _time_units(calendar="noleap"):
    return "days since 1850-01-01 00:00:00", calendar


def _encode_times(times):
    units, cal = _time_units()
    return nc.date2num(times, units=units, calendar=cal)


def _add_latlon(ds):
    lat = ds.createVariable("lat", "f4", ("lat",))
    lat.units = "degrees_north"
    lat.axis = "Y"
    lat[:] = LATS

    lon = ds.createVariable("lon", "f4", ("lon",))
    lon.units = "degrees_east"
    lon.axis = "X"
    lon[:] = LONS


def _add_time(ds, times):
    ds.createDimension("time", len(times))
    tv = ds.createVariable("time", "f8", ("time",))
    tv.units, tv.calendar = _time_units()
    tv.axis = "T"
    tv[:] = _encode_times(times)
    return tv


def _write_lev_dims(ds):
    """Write shared lev/ap/b dimensions into a 6hrLev file."""
    lv = ds.createVariable("lev", "f8", ("lev",))
    lv.units = "1"
    lv[:] = np.arange(1, NLEV + 1, dtype=np.float64)
    apv = ds.createVariable("ap", "f8", ("lev",))
    apv.units = "Pa"
    apv[:] = AP
    bv = ds.createVariable("b", "f8", ("lev",))
    bv.units = "1"
    bv[:] = B


def make_6hrLev():
    """6hrLev: one file per variable (CMIP6 convention)."""
    TRANGE = "19900101-19900102"
    NT = len(TIMES_6H)

    # ta
    for vn, units, vals in [
        ("ta",  "K",        270.0 + np.random.randn(NT, NLEV, NLAT, NLON)),
        ("ua",  "m s-1",    np.random.randn(NT, NLEV, NLAT, NLON) * 10),
        ("va",  "m s-1",    np.random.randn(NT, NLEV, NLAT, NLON) * 10),
        ("hus", "kg kg-1",  np.abs(np.random.randn(NT, NLEV, NLAT, NLON)) * 0.005 + 0.001),
    ]:
        fname = f"{vn}_6hrLev_{MODEL}_{EXP}_{MEM}_{GRID}_{TRANGE}.nc"
        path = os.path.join(OUTDIR, fname)
        print(f"Writing {fname}")
        with nc.Dataset(path, "w") as ds:
            ds.createDimension("lat", NLAT)
            ds.createDimension("lon", NLON)
            ds.createDimension("lev", NLEV)
            _add_time(ds, TIMES_6H)
            _add_latlon(ds)
            _write_lev_dims(ds)
            v = ds.createVariable(vn, "f4", ("time", "lev", "lat", "lon"),
                                  fill_value=1e20)
            v.units = units
            v[:] = vals
        print(f"  -> {os.path.getsize(path) // 1024} KB")

    # ps: 2D
    fname = f"ps_6hrLev_{MODEL}_{EXP}_{MEM}_{GRID}_{TRANGE}.nc"
    path = os.path.join(OUTDIR, fname)
    print(f"Writing {fname}")
    with nc.Dataset(path, "w") as ds:
        ds.createDimension("lat", NLAT)
        ds.createDimension("lon", NLON)
        ds.createDimension("lev", NLEV)
        _add_time(ds, TIMES_6H)
        _add_latlon(ds)
        _write_lev_dims(ds)
        ps = ds.createVariable("ps", "f4", ("time", "lat", "lon"),
                               fill_value=1e20)
        ps.units = "Pa"
        ps[:] = 100000.0 + np.random.randn(NT, NLAT, NLON) * 200
    print(f"  -> {os.path.getsize(path) // 1024} KB")


def make_6hrPlevPt():
    """6hrPlevPt: zg psl — on standard pressure levels."""
    fname = (f"zg_6hrPlevPt_{MODEL}_{EXP}_{MEM}_{GRID}_"
             f"19900101-19900102.nc")
    path = os.path.join(OUTDIR, fname)
    print(f"Writing {fname}")
    with nc.Dataset(path, "w") as ds:
        ds.createDimension("lat",  NLAT)
        ds.createDimension("lon",  NLON)
        ds.createDimension("plev", NPLEV)

        _add_time(ds, TIMES_6H)
        _add_latlon(ds)

        plv = ds.createVariable("plev", "f8", ("plev",))
        plv.units = "Pa"
        plv[:] = PLEV_HPA

        # zg: geopotential height (m) — roughly 200–13000 m
        zg = ds.createVariable("zg", "f4", ("time", "plev", "lat", "lon"),
                               fill_value=1e20)
        zg.units = "m"
        zg[:] = np.array([[[12000.0 + 1000.0 * j / NLAT for _ in range(NLON)]
                            for j in range(NLAT)]
                           for _ in range(len(TIMES_6H))]).reshape(
                               len(TIMES_6H), 1, NLAT, NLON) * np.array(
                               [1.0, 0.5]).reshape(1, 2, 1, 1)

        # psl: mean sea-level pressure
        psl = ds.createVariable("psl", "f4", ("time", "lat", "lon"),
                                fill_value=1e20)
        psl.units = "Pa"
        psl[:] = 101325.0 + np.random.randn(len(TIMES_6H), NLAT, NLON) * 300

    # psl in its own file
    fname2 = (f"psl_6hrPlevPt_{MODEL}_{EXP}_{MEM}_{GRID}_"
              f"19900101-19900102.nc")
    path2 = os.path.join(OUTDIR, fname2)
    print(f"Writing {fname2}")
    with nc.Dataset(path2, "w") as ds:
        ds.createDimension("lat", NLAT)
        ds.createDimension("lon", NLON)
        _add_time(ds, TIMES_6H)
        _add_latlon(ds)
        psl = ds.createVariable("psl", "f4", ("time", "lat", "lon"),
                                fill_value=1e20)
        psl.units = "Pa"
        psl[:] = 101325.0 + np.random.randn(len(TIMES_6H), NLAT, NLON) * 300
    print(f"  -> {os.path.getsize(path2) // 1024} KB")


def make_3hr():
    """3hr: tas uas vas huss — surface."""
    for vn, units, scale in [
        ("tas",  "K",        270.0),
        ("uas",  "m s-1",    0.0),
        ("vas",  "m s-1",    0.0),
        ("huss", "kg kg-1",  0.005),
    ]:
        fname = (f"{vn}_3hr_{MODEL}_{EXP}_{MEM}_{GRID}_"
                 f"199001010000-199001020000.nc")
        path = os.path.join(OUTDIR, fname)
        print(f"Writing {fname}")
        with nc.Dataset(path, "w") as ds:
            ds.createDimension("lat", NLAT)
            ds.createDimension("lon", NLON)
            _add_time(ds, TIMES_6H)
            _add_latlon(ds)
            v = ds.createVariable(vn, "f4", ("time", "lat", "lon"),
                                  fill_value=1e20)
            v.units = units
            v[:] = scale + np.random.randn(len(TIMES_6H), NLAT, NLON) * 1.0
        print(f"  -> {os.path.getsize(path) // 1024} KB")


def make_tos():
    """Oday: tos — SST."""
    fname = (f"tos_Oday_{MODEL}_{EXP}_{MEM}_{GRID}_"
             f"19900101-19900103.nc")
    path = os.path.join(OUTDIR, fname)
    print(f"Writing {fname}")
    with nc.Dataset(path, "w") as ds:
        ds.createDimension("lat", NLAT)
        ds.createDimension("lon", NLON)
        _add_time(ds, TIMES_DAY)
        _add_latlon(ds)
        tos = ds.createVariable("tos", "f4", ("time", "lat", "lon"),
                                fill_value=1e20)
        tos.units = "degC"
        tos[:] = 20.0 + np.random.randn(len(TIMES_DAY), NLAT, NLON) * 2
    print(f"  -> {os.path.getsize(path) // 1024} KB")


def make_Lmon():
    """Lmon: tsl mrsos — monthly soil."""
    # tsl: soil temperature on 4 depth layers
    fname_tsl = (f"tsl_Lmon_{MODEL}_{EXP}_{MEM}_{GRID}_"
                 f"198912-199002.nc")
    path = os.path.join(OUTDIR, fname_tsl)
    print(f"Writing {fname_tsl}")
    with nc.Dataset(path, "w") as ds:
        ds.createDimension("lat",   NLAT)
        ds.createDimension("lon",   NLON)
        ds.createDimension("depth", NSOIL)
        _add_time(ds, TIMES_MON)
        _add_latlon(ds)
        dv = ds.createVariable("depth", "f4", ("depth",))
        dv.units = "m"
        dv[:] = SOIL_DEPTHS
        tsl = ds.createVariable("tsl", "f4", ("time", "depth", "lat", "lon"),
                                fill_value=1e20)
        tsl.units = "K"
        tsl[:] = 275.0 + np.random.randn(len(TIMES_MON), NSOIL, NLAT, NLON) * 5
    print(f"  -> {os.path.getsize(path) // 1024} KB")

    # mrsos: top 10 cm soil moisture (single layer, kg m-2)
    fname_mr = (f"mrsos_Lmon_{MODEL}_{EXP}_{MEM}_{GRID}_"
                f"198912-199002.nc")
    path = os.path.join(OUTDIR, fname_mr)
    print(f"Writing {fname_mr}")
    with nc.Dataset(path, "w") as ds:
        ds.createDimension("lat", NLAT)
        ds.createDimension("lon", NLON)
        _add_time(ds, TIMES_MON)
        _add_latlon(ds)
        mr = ds.createVariable("mrsos", "f4", ("time", "lat", "lon"),
                               fill_value=1e20)
        mr.units = "kg m-2"
        mr[:] = 50.0 + np.random.randn(len(TIMES_MON), NLAT, NLON) * 5
    print(f"  -> {os.path.getsize(path) // 1024} KB")


if __name__ == "__main__":
    np.random.seed(42)
    print(f"Generating fake CESM2 data in: {OUTDIR}")
    make_6hrLev()
    make_6hrPlevPt()
    make_3hr()
    make_tos()
    make_Lmon()
    print("\nDone. Run: conda run -n uranus-cmip python3 run_c2w.py -m CESM2")
