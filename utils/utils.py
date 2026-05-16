#/usr/bin/env python
"""Commonly used utilities"""
import logging
import struct

import numpy as np

from utils.grid import OutputGrid


# Backwards-compat module-level constants. Derived from a default
# OutputGrid so any old caller importing utils.NLAT / utils.LATS etc.
# continues to see the historical 1deg-global / 14-plev / 4-soil values.
_DEFAULT_GRID = OutputGrid()
NLAT, NLON = _DEFAULT_GRID.nlat, _DEFAULT_GRID.nlon
LATS = _DEFAULT_GRID.lats
LONS = _DEFAULT_GRID.lons
PLVS = _DEFAULT_GRID.plev
SOIL_LVS = _DEFAULT_GRID.soil_layers

# WRF intermediate "surface" XLVL sentinel — meaning the slab is a 2-D
# surface field (2-m, 10-m, ground), not a pressure level.
XLVL_SURFACE = 200100.0


def throw_error(msg):
    '''
    throw error and exit
    '''
    logging.error(msg)

    exit()

def write_log(msg, lvl=20):
    '''
    write logging log to log file
    level code:
        CRITICAL    50
        ERROR   40
        WARNING 30
        INFO    20
        DEBUG   10
        NOTSET  0
    '''

    logging.log(lvl, msg)


def gen_wrf_mid_template(grid=None):
    '''Build the slab template dict for one WRF-intermediate record.

    `grid` is an OutputGrid; if omitted, the historical default 1deg global
    grid is used (preserves behavior for any caller that did not pass one).
    '''
    if grid is None:
        grid = _DEFAULT_GRID
    slab_dict={
        'IFV':5, 'HDATE':'0000-00-00_00:00:00:0000',
        'XFCST':0.0, 'MAP_SOURCE':'CMIP6',
        'FIELD':'', 'UNIT':'', 'DESC':'',
        'XLVL':0.0, 'NX':grid.nlon, 'NY':grid.nlat,
        'IPROJ':0,'STARTLOC':'SWCORNER',
        'STARTLAT':grid.lat_start, 'STARTLON':grid.lon_start,
        'DELTLAT':grid.deltlat, 'DELTLON':grid.deltlon,
        'EARTH_RAD':grid.earth_rad,
        'IS_WIND_EARTH_REL': 0,
        'SLAB':np.array(np.zeros((grid.nlat,grid.nlon)), dtype=np.float32),
        'key_lst':['IFV', 'HDATE', 'XFCST', 'MAP_SOURCE', 'FIELD', 'UNIT',
        'DESC', 'XLVL', 'NX', 'NY', 'IPROJ', 'STARTLOC',
        'STARTLAT', 'STARTLON', 'DELTLAT', 'DELTLON',
        'EARTH_RAD', 'IS_WIND_EARTH_REL', 'SLAB']
    }
    return slab_dict

def write_record(out_file, slab_dic):
    '''
    Write a record to a WRF intermediate file
    '''
    slab_dic['MAP_SOURCE']='CMIP6'.ljust(32)
    slab_dic['FIELD']=slab_dic['FIELD'].ljust(9)
    slab_dic['UNIT']=slab_dic['UNIT'].ljust(25)
    slab_dic['DESC']=slab_dic['DESC'].ljust(46)

    # IFV header
    out_file.write_record(struct.pack('>I',slab_dic['IFV']))

    # HDATE header
    pack=struct.pack('>24sf32s9s25s46sfIII',
        slab_dic['HDATE'].encode(), slab_dic['XFCST'],
        slab_dic['MAP_SOURCE'].encode(), slab_dic['FIELD'].encode(),
        slab_dic['UNIT'].encode(), slab_dic['DESC'].encode(),
        slab_dic['XLVL'], slab_dic['NX'], slab_dic['NY'],
        slab_dic['IPROJ'])
    out_file.write_record(pack)

    # STARTLOC header
    pack=struct.pack('>8sfffff',
        slab_dic['STARTLOC'].encode(), slab_dic['STARTLAT'],
        slab_dic['STARTLON'], slab_dic['DELTLAT'], slab_dic['DELTLON'],
        slab_dic['EARTH_RAD'])
    out_file.write_record(pack)

    # IS_WIND_EARTH_REL header
    pack=struct.pack('>I', slab_dic['IS_WIND_EARTH_REL'])
    out_file.write_record(pack)

    # Let's play with the SLAB
    out_file.write_record(
        slab_dic['SLAB'].astype('>f'))


def fill_nan_2d_nearest(arr):
    '''Fill every NaN in a 2-D array with the value of its nearest non-NaN
    neighbour (2-D Euclidean). Used to extend land-only fields over ocean
    and vice versa, so xarray.interp does not produce wild extrapolations
    when crossing the coastline.'''
    from scipy.ndimage import distance_transform_edt
    mask = np.isnan(arr)
    if not mask.any():
        return arr
    if mask.all():
        return arr
    # indices of the nearest non-NaN cell for every grid point
    _, (yi, xi) = distance_transform_edt(mask, return_distances=True,
                                         return_indices=True)
    return arr[yi, xi]


def hybrid2pressure(da, ap, b, ps, plev=None):
    '''
    Convert hybrid sigma-pressure levels to standard pressure levels.

    da : DataArray (lev, lat, lon) — field on hybrid levels
    ap : 1-D array (Pa) — hybrid coefficient ap
    b  : 1-D array      — hybrid coefficient b
    ps : DataArray (lat, lon) — surface pressure (Pa)
    plev : 1-D array of target pressure levels in Pa. Defaults to the
           module-level PLVS for backwards compatibility.
    Returns DataArray (plev, lat, lon).
    '''
    import xarray as xr
    if plev is None:
        plev = PLVS
    plev = np.asarray(plev)
    nz, nlat, nlon = da.values.shape

    # pressure at each hybrid level: p(k) = ap(k) + b(k)*ps
    # shape → (nz, nlat, nlon)
    pa3d = ap[:, np.newaxis, np.newaxis] + b[:, np.newaxis, np.newaxis] * ps.values[np.newaxis, :, :]

    out = np.empty((len(plev), nlat, nlon), dtype=np.float32)
    for idz, plv in enumerate(plev):
        # nearest hybrid level in pressure space for each column
        diff = np.abs(pa3d - plv)         # (nz, nlat, nlon)
        idx2d = np.argmin(diff, axis=0)   # (nlat, nlon)
        out[idz] = da.values[idx2d,
                              np.arange(nlat)[:, np.newaxis],
                              np.arange(nlon)[np.newaxis, :]]

    return xr.DataArray(
        out,
        dims=['plev', 'lat', 'lon'],
        coords={
            'plev': plev,
            'lat':  da.coords['lat'],
            'lon':  da.coords['lon'],
        }
    )
