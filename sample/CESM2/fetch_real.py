#!/usr/bin/env python3
"""
Download a 2-day subset (1990-01-01 to 1990-01-02) of real CESM2 CMIP6 data
from NCAR's ESGF node via OPeNDAP, saving to this directory.

Variables available on ESGF for CESM2 historical r11i1p1f1:
  6hrLev : ta, ua, va, hus, ps  (all from esgf-data.ucar.edu)
  Oday   : tos (gr grid → renamed to gn; regular 180x360)
  Lmon   : tsl, mrsos (gn grid, esgf-data.ucar.edu)

NOT available: 3hr (tas/uas/vas/huss) and 6hrPlevPt (zg/psl) — CESM2 did
not submit these to ESGF.  The pipeline skips them gracefully.

Notes:
  - tos native-grid (gn) is the POP curvilinear ocean grid with 2-D lat/lon
    which cannot be interpolated with xarray.interp. We download the regridded
    version (gr: regular 180x360 1-degree) and save it under the gn filename
    so the pipeline (grid_flag=gn) can discover it.
  - OPeNDAP requests are capped at 500 MB; Lmon files need a time slice.

Run:
    conda run -n uranus-cmip python3 sample/CESM2/fetch_real.py
"""

import os, cftime
import xarray as xr

OUTDIR = os.path.dirname(os.path.abspath(__file__))
NCAR = 'https://esgf-data.ucar.edu/thredds/dodsC/esg_dataroot/CMIP6/CMIP/NCAR/CESM2/historical/r11i1p1f1'

T0 = cftime.DatetimeNoLeap(1990, 1, 1, 0)
T1 = cftime.DatetimeNoLeap(1990, 1, 2, 0)

# ── 6hrLev ────────────────────────────────────────────────────────────────────
LEV_VARS = [
    ('ta',  'v20200210'),
    ('ua',  'v20190514'),
    ('va',  'v20190514'),
    ('hus', 'v20190514'),
    ('ps',  'v20190514'),
]

for var, ver in LEV_VARS:
    trange  = '199001010000-199912311800'
    fname   = f'{var}_6hrLev_CESM2_historical_r11i1p1f1_gn_{trange}.nc'
    outpath = os.path.join(OUTDIR, fname)
    if os.path.exists(outpath):
        print(f'Already exists: {fname}')
        continue
    url = f'{NCAR}/6hrLev/{var}/gn/{ver}/{fname}'
    print(f'Fetching {var} via OPeNDAP …')
    ds  = xr.open_dataset(url, engine='netcdf4', use_cftime=True)
    sub = ds.sel(time=slice(T0, T1))
    print(f'  shape: {sub[var].shape}  →  {outpath}')
    sub.to_netcdf(outpath)
    ds.close()
    print(f'  saved ({os.path.getsize(outpath)//1024//1024} MB)')

# ── Oday / tos ────────────────────────────────────────────────────────────────
# Use the regridded (gr) version: regular 180x360 1-D lat/lon, compatible with
# xarray.interp.  Save under the gn filename so glob(grid_flag=gn) finds it.
TOS_OUT_FNAME = 'tos_Oday_CESM2_historical_r11i1p1f1_gn_19500102-20000101.nc'
TOS_OUT = os.path.join(OUTDIR, TOS_OUT_FNAME)
if not os.path.exists(TOS_OUT):
    # Remove incorrectly downloaded native-grid file if present
    bad = os.path.join(OUTDIR, TOS_OUT_FNAME)
    if os.path.exists(bad):
        os.remove(bad)
    gr_chunk = 'tos_Oday_CESM2_historical_r11i1p1f1_gr_19500102-20000101.nc'
    url = f'{NCAR}/Oday/tos/gr/v20190514/{gr_chunk}'
    print('Fetching tos (gr→gn) via OPeNDAP …')
    ds  = xr.open_dataset(url, engine='netcdf4', use_cftime=True)
    t_jan = cftime.DatetimeNoLeap(1990, 1, 1)
    t_feb = cftime.DatetimeNoLeap(1990, 2, 1)
    sub = ds.sel(time=slice(t_jan, t_feb))
    print(f'  shape: {sub["tos"].shape}  →  {TOS_OUT}')
    sub.to_netcdf(TOS_OUT)
    ds.close()
    print(f'  saved ({os.path.getsize(TOS_OUT)//1024//1024} MB)')
else:
    print(f'Already exists: {TOS_OUT_FNAME}')

# ── Lmon / tsl + mrsos ────────────────────────────────────────────────────────
# Subset to 3 months around the ETL window to stay under the 500 MB OPeNDAP limit.
# The pipeline selects the nearest monthly step for the 1990-01-01 target.
for var in ['tsl', 'mrsos']:
    chunk   = f'{var}_Lmon_CESM2_historical_r11i1p1f1_gn_195001-199912.nc'
    outpath = os.path.join(OUTDIR, chunk)
    if os.path.exists(outpath):
        print(f'Already exists: {chunk}')
        continue
    url = f'{NCAR}/Lmon/{var}/gn/v20190514/{chunk}'
    print(f'Fetching {var} (Lmon) via OPeNDAP, subsetting Dec 1989–Feb 1990 …')
    ds  = xr.open_dataset(url, engine='netcdf4', use_cftime=True)
    t_beg = cftime.DatetimeNoLeap(1989, 12, 1)
    t_end = cftime.DatetimeNoLeap(1990,  3, 1)
    sub = ds.sel(time=slice(t_beg, t_end))
    print(f'  shape: {sub[var].shape}  →  {outpath}')
    sub.to_netcdf(outpath)
    ds.close()
    print(f'  saved ({os.path.getsize(outpath)//1024//1024} MB)')

print('\nDone.  Run: conda run -n uranus-cmip python3 run_c2w.py -m CESM2')
