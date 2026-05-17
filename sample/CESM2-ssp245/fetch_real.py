#!/usr/bin/env python3
"""Fetch a 2-day real CESM2 SSP245 smoke-test subset via OPeNDAP.

The CMIP6 ScenarioMIP CESM2 SSP245 high-frequency holdings are sparse but
sufficient for the core CESM2 adapter path:

  6hrLev  ta, ua, va, hus, ps   r11i1p1f1 only among supported variants
  6hrPlev psl
  day     tas, huss             daily fallback for near-surface fields
  Amon    ts                    monthly skin temperature fallback
  Oday    tos                   native ocean grid, regridded here to 1-D lat/lon
  Lmon    tsl, mrsos            monthly soil
  fx      orog, sftlf

Run from the repository root on hqlx74:
    conda run -n uranus-cmip python3 sample/CESM2-ssp245/fetch_real.py
"""

import os
from pathlib import Path

import cftime
import numpy as np
import xarray as xr


OUTDIR = Path(__file__).resolve().parent
MODEL = "CESM2"
EXP = "ssp245"
MEM = "r11i1p1f1"
GRID = "gn"
VER = "v20200528"

UCAR = (
    "http://esgf-data.ucar.edu/thredds/dodsC/esg_dataroot/CMIP6/"
    f"ScenarioMIP/NCAR/{MODEL}/{EXP}/{MEM}"
)
ORNL = (
    "https://esgf-node.ornl.gov/thredds/dodsC/css03_data/CMIP6/"
    f"ScenarioMIP/NCAR/{MODEL}/{EXP}/{MEM}"
)

T0_6H = cftime.DatetimeNoLeap(2015, 1, 1, 0)
T1_6H = cftime.DatetimeNoLeap(2015, 1, 2, 0)
T0_DAY = cftime.DatetimeNoLeap(2015, 1, 1)
T1_DAY = cftime.DatetimeNoLeap(2015, 1, 3)
T0_MON = cftime.DatetimeNoLeap(2015, 1, 1)
T1_MON = cftime.DatetimeNoLeap(2015, 2, 1)


def _open(urls):
    last = None
    for url in urls:
        try:
            print(f"  opening {url}")
            return xr.open_dataset(url, engine="netcdf4", use_cftime=True)
        except Exception as exc:
            last = exc
            print(f"  failed: {exc}")
    raise RuntimeError(f"all OPeNDAP endpoints failed: {last}")


def _save_subset(urls, var, out_name, t0=None, t1=None):
    out = OUTDIR / out_name
    if out.exists():
        print(f"Already exists: {out.name}")
        return
    print(f"Fetching {var} -> {out.name}")
    ds = _open(urls)
    try:
        sub = ds.sel(time=slice(t0, t1)) if t0 is not None else ds
        sub.to_netcdf(out)
        print(f"  saved {out.name} ({out.stat().st_size // 1024 // 1024} MB)")
    finally:
        ds.close()


def _urls(table, var, chunk, grid=GRID):
    rel = f"{table}/{var}/{grid}/{VER}/{chunk}"
    return [f"{UCAR}/{rel}", f"{ORNL}/{rel}"]


def _regrid_tos_to_regular(urls, out_name):
    out = OUTDIR / out_name
    if out.exists():
        print(f"Already exists: {out.name}")
        return

    print(f"Fetching tos and regridding native ocean grid -> {out.name}")
    ds = _open(urls)
    try:
        sub = ds.sel(time=slice(T0_DAY, T1_DAY))
        da = sub["tos"]

        if da["lat"].ndim == 1 and da["lon"].ndim == 1:
            da.to_dataset(name="tos").to_netcdf(out)
            print(f"  saved regular-grid tos ({out.stat().st_size // 1024 // 1024} MB)")
            return

        from scipy.interpolate import griddata

        lat2d = np.asarray(da["lat"].values)
        lon2d = np.asarray(da["lon"].values) % 360.0
        good = np.isfinite(lat2d) & np.isfinite(lon2d)
        points = np.column_stack((lat2d[good], lon2d[good]))

        lat = np.arange(-89.5, 90.0, 1.0, dtype=np.float32)
        lon = np.arange(0.5, 360.0, 1.0, dtype=np.float32)
        lon_grid, lat_grid = np.meshgrid(lon, lat)
        target = np.column_stack((lat_grid.ravel(), lon_grid.ravel()))

        slabs = []
        for it in range(da.sizes["time"]):
            src = np.asarray(da.isel(time=it).values)
            vals = src[good]
            lin = griddata(points, vals, target, method="linear")
            near = griddata(points, vals, target, method="nearest")
            filled = np.where(np.isfinite(lin), lin, near)
            slabs.append(filled.reshape(lat.size, lon.size).astype(np.float32))

        out_da = xr.DataArray(
            np.stack(slabs, axis=0),
            dims=("time", "lat", "lon"),
            coords={"time": da["time"].values, "lat": lat, "lon": lon},
            name="tos",
            attrs=dict(da.attrs),
        )
        out_da.to_dataset().to_netcdf(out)
        print(f"  saved regridded tos ({out.stat().st_size // 1024 // 1024} MB)")
    finally:
        ds.close()


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)

    for var in ("ta", "ua", "va", "hus", "ps"):
        chunk = f"{var}_6hrLev_{MODEL}_{EXP}_{MEM}_{GRID}_201501010000-202412311800.nc"
        out = f"{var}_6hrLev_{MODEL}_{EXP}_{MEM}_{GRID}_201501010000-201501020000.nc"
        _save_subset(_urls("6hrLev", var, chunk), var, out, T0_6H, T1_6H)

    chunk = f"psl_6hrPlev_{MODEL}_{EXP}_{MEM}_{GRID}_201501010000-202412311800.nc"
    out = f"psl_6hrPlev_{MODEL}_{EXP}_{MEM}_{GRID}_201501010000-201501020000.nc"
    _save_subset(_urls("6hrPlev", "psl", chunk), "psl", out, T0_6H, T1_6H)

    for var in ("tas", "huss"):
        chunk = f"{var}_day_{MODEL}_{EXP}_{MEM}_{GRID}_20150101-20241231.nc"
        out = f"{var}_day_{MODEL}_{EXP}_{MEM}_{GRID}_20150101-20150103.nc"
        _save_subset(_urls("day", var, chunk), var, out, T0_DAY, T1_DAY)

    chunk = f"ts_Amon_{MODEL}_{EXP}_{MEM}_{GRID}_201501-206412.nc"
    out = f"ts_Amon_{MODEL}_{EXP}_{MEM}_{GRID}_201501-201502.nc"
    _save_subset(_urls("Amon", "ts", chunk), "ts", out, T0_MON, T1_MON)

    for var in ("tsl", "mrsos"):
        chunk = f"{var}_Lmon_{MODEL}_{EXP}_{MEM}_{GRID}_201501-206412.nc"
        out = f"{var}_Lmon_{MODEL}_{EXP}_{MEM}_{GRID}_201501-201502.nc"
        _save_subset(_urls("Lmon", var, chunk), var, out, T0_MON, T1_MON)

    for var in ("orog", "sftlf"):
        chunk = f"{var}_fx_{MODEL}_{EXP}_{MEM}_{GRID}.nc"
        _save_subset(_urls("fx", var, chunk), var, chunk)

    chunk = f"tos_Oday_{MODEL}_{EXP}_{MEM}_{GRID}_20150102-20650101.nc"
    out = f"tos_Oday_{MODEL}_{EXP}_{MEM}_{GRID}_20150102-20150103.nc"
    _regrid_tos_to_regular(_urls("Oday", "tos", chunk), out)

    print("\nDone. Run: conda run -n uranus-cmip python3 run_c2w.py -m CESM2-ssp245")


if __name__ == "__main__":
    main()
