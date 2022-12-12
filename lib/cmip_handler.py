#/usr/bin/env python3
"""Build Observation Station Objects"""

import datetime
import struct
import pandas as pd 
import xarray as xr
import numpy as np
from scipy.io import FortranFile
from utils import utils
from scipy.interpolate import griddata


print_prefix='lib.cmip_container>>'

# below for interp constants
# All source data from various models are interpolated to the same mesh.

NLAT,NLON=181,360

new_lat = np.linspace(-90, 90., NLAT)
new_lon = np.linspace(0., 359, NLON)
new_lv = 100.0*np.array([1000.0, 925.0, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50])
NLV=len(new_lv)

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

class CMIPHandler(object):

    '''
    Construct CMIP Handler 

    Methods
    -----------
    __init__:   initialize CMIP Handler with config and loading data
    interp_data: interpolate data to common mesh
    write_wrfinterm: write wrfinterm file

    '''
    
    def __init__(self, cfg):
        '''
        Initialize CMIP Handler with config and loading data
        '''
        
        in_cfg=cfg['INPUT']
        out_cfg=cfg['OUTPUT']

        self.model_name=in_cfg['model_name']
        self.cmip_strt_ts=in_cfg['cmip_strt_ts']
        self.cmip_end_ts=in_cfg['cmip_end_ts']
        self.cimp_frq=in_cfg['cmip_frq']

        vtable=in_cfg['vtable_name'].replace('@model',self.model_name)
        self.vtable=pd.read_csv('./db/'+vtable+'.csv')

        self.etl_strt_time=datetime.datetime.strptime(out_cfg['etl_strt_ts'],'%Y%m%d%H%M')
        self.etl_end_time=datetime.datetime.strptime(out_cfg['etl_end_ts'],'%Y%m%d%H%M')
        self.out_root=out_cfg['output_root']
        self.out_prefix=out_cfg['output_prefix']

        # wrf intermidiate slab template
        self.mtemplate=gen_wrf_mid_template()

        dt=datetime.timedelta(hours=int(self.cimp_frq))
        self.out_time_series=pd.date_range(
            start=self.etl_strt_time, end=self.etl_end_time, freq=dt)
        # init empty cmip container dict
        self.ds, self.outfrm={},{}

        self.out_slab=gen_wrf_mid_template()


        for idx, itm in self.vtable.iterrows():
            varname=itm['src_v']
            lvlmark=itm['lvlmark']
            if lvlmark == 'None':
                lvlmark=''
            # repeat level to pad missing soil layers
            if itm['type'] == '2d-soilr':
                continue
            
            fn=in_cfg['input_root']+'/'+varname+'_'+in_cfg['cmip_frq']+'hr'+lvlmark+'_'+in_cfg['model_name']
            fn=fn+'_'+in_cfg['exp_id']+'_'+in_cfg['esm_flag']+'_'+in_cfg['grid_flag']
            fn+='_'+in_cfg['cmip_strt_ts']+'-'+in_cfg['cmip_end_ts']+'.nc'
            
            utils.write_log(print_prefix+'Loading '+fn)
            ds=xr.open_dataset(fn)
            self.ds[varname]=ds[varname].sel(
                time=slice(self.etl_strt_time,self.etl_end_time))
            ds.close()

    def interp_data(self, tf):
        '''
        Interpolate data to common mesh
        '''

        for idx, itm in self.vtable.iterrows():
            varname=itm['src_v']
            lvltype=itm['type']
            
            # repeat level to pad missing soil layers
            if lvltype == '2d-soilr':
                continue

            ds=self.ds[varname].sel(time=tf)
          
            if varname =='mrsos':
                ds.values=ds.values*1e-2

            if varname =='tos' and itm['units']=='degC':
                ds.values=ds.values+273.15
                itm['units']='K'

            if lvltype=='3d':
                self.outfrm[varname]=ds.interp(lat=new_lat, lon=new_lon, plev=new_lv,
                        method='linear',kwargs={"fill_value": "extrapolate"})
            elif lvltype=='2d':
                if varname=='tos':
                    ocn_da=ds.interpolate_na(dim='j',
                        method='linear',fill_value="extrapolate")
                    grid_x,grid_y=np.meshgrid(new_lon,new_lat)
                    values=ocn_da.values
                    points=np.array(
                        [ds.latitude.values.flatten(),ds.longitude.values.flatten()]).T
                    grid_z0 = griddata(
                        points, values.flatten(), 
                        (grid_x, grid_y), method='nearest')
                    self.outfrm[varname]=grid_z0
                else:
                    self.outfrm[varname]=ds.interp(lat=new_lat, lon=new_lon,
                        method='linear',kwargs={"fill_value": "extrapolate"})
            
            elif lvltype=='2d-soil':
                ds=ds.interpolate_na(
                    dim="lon", method="linear",fill_value="extrapolate")
                
                self.outfrm[varname]=ds.interp(lat=new_lat, lon=new_lon,
                        method='linear',kwargs={"fill_value": "extrapolate"})

    
    def write_wrfinterm(self, tf):
        out_fn=self.out_root+'/'+self.out_prefix+':'+tf.strftime('%Y-%m-%d_%H')
        
        utils.write_log(print_prefix+'Writing '+out_fn)
        # dtype='>u4' for header (big-endian, unsigned int)
        wrf_mid = FortranFile(out_fn, 'w', header_dtype=np.dtype('>u4'))
        
        out_dic=self.out_slab
        out_dic['HDATE']=tf.strftime('%Y-%m-%d_%H:%M:%S:0000')

        for idx, itm in self.vtable.iterrows():

            varname=itm['src_v']
            lvltype=itm['type']
            out_dic['FIELD']=itm['aim_v']
            
            out_dic['UNIT']=itm['units']
            if varname=='tos':
                out_dic['UNIT']='K'

            out_dic['DESC']=itm['desc']
            
            out_dic['XLVL']=200100.0
            if lvltype=='3d':
                for lvl in new_lv:
                    out_dic['XLVL']=lvl
                    out_dic['SLAB']=self.outfrm[varname].sel(plev=lvl).values
                    write_record(wrf_mid, out_dic)
            else:
                if varname=='tos':
                    out_dic['SLAB']=self.outfrm[varname]
                else:
                    out_dic['SLAB']=self.outfrm[varname].values
                write_record(wrf_mid, out_dic)
       
        wrf_mid.close()


if __name__ == "__main__":
    pass
