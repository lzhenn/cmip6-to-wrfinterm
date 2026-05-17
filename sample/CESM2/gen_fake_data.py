#!/usr/bin/env python3
"""
Generate minimal synthetic CESM2-format CMIP6 files for smoke-testing cmip6-to-wrfinterm.

Output: sample/CESM2/ (same dir as this script)
Files cover 1990-01-01 00:00 to 1990-01-02 00:00 (5 time steps at 6h).
Grid: 10x20 (lat x lon), 3 hybrid levels, 2 pressure levels, 4 soil layers.

Run:
    conda run -n uranus-cmip python3 sample/CESM2/gen_fake_data.py

Optional environment overrides for scenario smoke tests:
    CESM2_FAKE_EXP=ssp245 CESM2_FAKE_YEAR=2015 \
      conda run -n uranus-cmip python3 sample/CESM2/gen_fake_data.py
"""

import os
import numpy as np
import netCDF4 as nc
import cftime

OUTDIR = os.path.dirname(os.path.abspath(__file__))
MODEL = "CESM2"
MEM = os.environ.get("CESM2_FAKE_MEMBER", "r11i1p1f1")
GRID = os.environ.get("CESM2_FAKE_GRID", "gn")
EXP = os.environ.get("CESM2_FAKE_EXP", "historical")
START_YEAR = int(os.environ.get("CESM2_FAKE_YEAR", "1990"))
VER = "v20190313"

# Small grid for fast testing
NLAT, NLON = 10, 20
NLEV = 14      # hybrid model levels
NPLEV = 14     # pressure levels (6hrPlevPt)
NSOIL = 4      # soil layers

LATS = np.linspace(-90, 90, NLAT, dtype=np.float32)
LONS = np.linspace(0, 355, NLON, dtype=np.float32)

# Synthetic hybrid coefficients. B=0 makes these pressure-like levels, which
# keeps the WRF smoke test physically monotonic and deterministic.
PLEV_PA = np.array([
    100000.0, 92500.0, 85000.0, 70000.0, 60000.0, 50000.0, 40000.0,
    30000.0, 25000.0, 20000.0, 15000.0, 10000.0, 7000.0, 5000.0,
], dtype=np.float64)
AP = PLEV_PA.copy()
B  = np.zeros_like(AP)
P0 = 100000.0  # Pa

# Time: Jan 1 00Z to Jan 2 00Z, 5 steps × 6h
TIMES_6H = [
    cftime.DatetimeNoLeap(START_YEAR, 1, 1,  0),
    cftime.DatetimeNoLeap(START_YEAR, 1, 1,  6),
    cftime.DatetimeNoLeap(START_YEAR, 1, 1, 12),
    cftime.DatetimeNoLeap(START_YEAR, 1, 1, 18),
    cftime.DatetimeNoLeap(START_YEAR, 1, 2,  0),
]
# Monthly soil: just January
TIMES_MON = [cftime.DatetimeNoLeap(START_YEAR, 1, 16, 12)]
# Daily SST: 3 days around Jan 1
TIMES_DAY = [
    cftime.DatetimeNoLeap(START_YEAR, 1,  1),
    cftime.DatetimeNoLeap(START_YEAR, 1,  2),
    cftime.DatetimeNoLeap(START_YEAR, 1,  3),
]

PLEV_HPA = PLEV_PA.copy()  # Pa for 6hrPlevPt
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
    TRANGE = f"{START_YEAR}0101-{START_YEAR}0102"
    NT = len(TIMES_6H)
    zfac = np.linspace(0.0, 1.0, NLEV, dtype=np.float32)
    lat_term = (LATS / 90.0).reshape(1, 1, NLAT, 1)
    lon_term = np.sin(np.deg2rad(LONS)).reshape(1, 1, 1, NLON)
    time_term = np.arange(NT, dtype=np.float32).reshape(NT, 1, 1, 1)
    lev_term = zfac.reshape(1, NLEV, 1, 1)

    ta_vals = 292.0 - 65.0 * lev_term - 18.0 * np.abs(lat_term) + 0.2 * time_term
    ua_vals = 8.0 + 12.0 * lev_term + 1.5 * lon_term
    va_vals = 2.0 * lat_term + 0.5 * time_term
    hus_vals = 0.014 * np.exp(-4.0 * lev_term) * (1.0 - 0.4 * np.abs(lat_term))

    # ta
    for vn, units, vals in [
        ("ta",  "K",        ta_vals),
        ("ua",  "m s-1",    ua_vals),
        ("va",  "m s-1",    va_vals),
        ("hus", "kg kg-1",  hus_vals),
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
            v[:] = np.broadcast_to(vals, (NT, NLEV, NLAT, NLON))
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
        ps[:] = np.broadcast_to(
            100000.0 + 500.0 * np.cos(np.deg2rad(LATS))[:, None],
            (NT, NLAT, NLON))
    print(f"  -> {os.path.getsize(path) // 1024} KB")


def make_6hrPlevPt():
    """6hrPlevPt: zg psl — on standard pressure levels."""
    fname = (f"zg_6hrPlevPt_{MODEL}_{EXP}_{MEM}_{GRID}_"
             f"{START_YEAR}0101-{START_YEAR}0102.nc")
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

        # zg: geopotential height (m), increasing monotonically upward.
        zg = ds.createVariable("zg", "f4", ("time", "plev", "lat", "lon"),
                               fill_value=1e20)
        zg.units = "m"
        heights = np.array([
            100.0, 760.0, 1450.0, 3000.0, 4200.0, 5600.0, 7200.0,
            9200.0, 10300.0, 11800.0, 13800.0, 16200.0, 18400.0, 20500.0,
        ], dtype=np.float32)
        zg[:] = np.broadcast_to(
            heights.reshape(1, NPLEV, 1, 1)
            + 20.0 * (LATS / 90.0).reshape(1, 1, NLAT, 1),
            (len(TIMES_6H), NPLEV, NLAT, NLON))

        # psl: mean sea-level pressure
        psl = ds.createVariable("psl", "f4", ("time", "lat", "lon"),
                                fill_value=1e20)
        psl.units = "Pa"
        psl[:] = np.broadcast_to(
            101325.0 + 300.0 * np.cos(np.deg2rad(LATS))[:, None],
            (len(TIMES_6H), NLAT, NLON))

    # psl in its own file
    fname2 = (f"psl_6hrPlevPt_{MODEL}_{EXP}_{MEM}_{GRID}_"
              f"{START_YEAR}0101-{START_YEAR}0102.nc")
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
        psl[:] = np.broadcast_to(
            101325.0 + 300.0 * np.cos(np.deg2rad(LATS))[:, None],
            (len(TIMES_6H), NLAT, NLON))
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
                 f"{START_YEAR}01010000-{START_YEAR}01020000.nc")
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
             f"{START_YEAR}0101-{START_YEAR}0103.nc")
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


def make_Amon():
    """Amon: ts — monthly surface skin temperature."""
    fname = (f"ts_Amon_{MODEL}_{EXP}_{MEM}_{GRID}_"
             f"{START_YEAR - 1}12-{START_YEAR}02.nc")
    path = os.path.join(OUTDIR, fname)
    print(f"Writing {fname}")
    with nc.Dataset(path, "w") as ds:
        ds.createDimension("lat", NLAT)
        ds.createDimension("lon", NLON)
        _add_time(ds, TIMES_MON)
        _add_latlon(ds)
        ts = ds.createVariable("ts", "f4", ("time", "lat", "lon"),
                               fill_value=1e20)
        ts.units = "K"
        ts[:] = 280.0 + np.random.randn(len(TIMES_MON), NLAT, NLON) * 3
    print(f"  -> {os.path.getsize(path) // 1024} KB")


def make_fx():
    """fx: orog/sftlf — static surface fields."""
    fname_orog = f"orog_fx_{MODEL}_{EXP}_{MEM}_{GRID}.nc"
    path = os.path.join(OUTDIR, fname_orog)
    print(f"Writing {fname_orog}")
    with nc.Dataset(path, "w") as ds:
        ds.createDimension("lat", NLAT)
        ds.createDimension("lon", NLON)
        _add_latlon(ds)
        orog = ds.createVariable("orog", "f4", ("lat", "lon"),
                                 fill_value=1e20)
        orog.units = "m"
        ridge = np.maximum(0.0, 1200.0 * np.cos(np.deg2rad(LATS))[:, None])
        orog[:] = ridge + np.zeros((NLAT, NLON), dtype=np.float32)
    print(f"  -> {os.path.getsize(path) // 1024} KB")

    fname_sftlf = f"sftlf_fx_{MODEL}_{EXP}_{MEM}_{GRID}.nc"
    path = os.path.join(OUTDIR, fname_sftlf)
    print(f"Writing {fname_sftlf}")
    with nc.Dataset(path, "w") as ds:
        ds.createDimension("lat", NLAT)
        ds.createDimension("lon", NLON)
        _add_latlon(ds)
        sftlf = ds.createVariable("sftlf", "f4", ("lat", "lon"),
                                  fill_value=1e20)
        sftlf.units = "%"
        sftlf[:] = np.where(LATS[:, None] > -60.0, 100.0, 0.0)
    print(f"  -> {os.path.getsize(path) // 1024} KB")


def make_Lmon():
    """Lmon: tsl mrsos — monthly soil."""
    # tsl: soil temperature on 4 depth layers
    fname_tsl = (f"tsl_Lmon_{MODEL}_{EXP}_{MEM}_{GRID}_"
                 f"{START_YEAR - 1}12-{START_YEAR}02.nc")
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
                f"{START_YEAR - 1}12-{START_YEAR}02.nc")
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
    make_fx()
    make_6hrLev()
    make_6hrPlevPt()
    make_3hr()
    make_tos()
    make_Amon()
    make_Lmon()
    print("\nDone. Run: conda run -n uranus-cmip python3 run_c2w.py -m CESM2")
