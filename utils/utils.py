#/usr/bin/env python
"""Commonly used utilities"""
import logging
import struct

import numpy as np


# Consts
NLAT,NLON=181,360

LATS = np.linspace(-90, 90., NLAT)
LONS = np.linspace(0., 359, NLON)
PLVS = 100.0*np.array([1000.0, 925.0, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50])
SOIL_LVS=['000010','010040','040100','100200']

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


def gen_wrf_mid_template():
    slab_dict={
        'IFV':5, 'HDATE':'0000-00-00_00:00:00:0000',
        'XFCST':0.0, 'MAP_SOURCE':'CMIP6',
        'FIELD':'', 'UNIT':'', 'DESC':'', 
        'XLVL':0.0, 'NX':NLON, 'NY':NLAT,
        'IPROJ':0,'STARTLOC':'SWCORNER',
        'STARTLAT':-90.0, 'STARTLON':0.0,
        'DELTLAT':1.0, 'DELTLON':1.0, 'EARTH_RAD':6371.229,
        'IS_WIND_EARTH_REL': 0, 
        'SLAB':np.array(np.zeros((NLAT,NLON)), dtype=np.float32),
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


def hybrid2pressure(da,ap,b,ps):
    '''
    Convert hybrid level to pressure level
    '''
    #print(da.values.shape)
    nz, nlat, nlon=da.values.shape
    da_new=da.copy()[0:len(PLVS),:,:]
    da_new=da_new.rename({'lev':'plev'})
    da_new=da_new.assign_coords({'plev':new_lv})
    
    pa3d=np.broadcast_to(ps.values, (nz, nlat, nlon))
    pa3d=np.swapaxes(pa3d,0,2) 
    # get hybrid level
    pa3d=pa3d*b+ap
    for idz, plv in enumerate(PLVS):
        idx2d=np.sum(np.where(pa3d<plv,0,1),axis=2)-1
        idx2d=np.where(idx2d<0,0,idx2d)
        idx3d=np.broadcast_to(idx2d.T, (nz, nlat, nlon))
        temp=np.take_along_axis(da.values, idx3d, axis=0)
        da_new.values[idz,:,:]=temp[0,:,:]
    return da_new