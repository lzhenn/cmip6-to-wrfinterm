#/usr/bin/env python3
"""Build Observation Station Objects"""

import datetime
import pandas as pd 
import xarray as xr
import numpy as np
from scipy.io import FortranFile
from utils import utils
from scipy.interpolate import griddata


print_prefix='lib.cmip_container>>'

# below for interp constants
# All source data from various models are interpolated to the same mesh.


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
        Initialize CMIP Handler with config and load data
        '''
        
        in_cfg=cfg['INPUT']
        out_cfg=cfg['OUTPUT']

        self.model_name=in_cfg['model_name']
        self.scenario=in_cfg['scenario']
        if 'cmip_strt_ts' in in_cfg: # exists
            self.cmip_strt_ts=in_cfg['cmip_strt_ts']
            self.cmip_end_ts=in_cfg['cmip_end_ts']

        self.etl_strt_time=datetime.datetime.strptime(
            out_cfg['etl_strt_ts'],'%Y%m%d%H%M')
        self.etl_end_time=datetime.datetime.strptime(
            out_cfg['etl_end_ts'],'%Y%m%d%H%M')
        self.in_root=in_cfg['input_root']
        self.out_root=out_cfg['output_root']

        self._build_meta()
        self._load_cmip_data()        
        self.out_slab=utils.gen_wrf_mid_template()


    def _build_meta(self):
        '''
        Build metadata for model and scenario
        '''
        df_meta=pd.read_csv('./db/cmip6_meta.csv')
        meta_scenario='ssp' if self.scenario[0:3]=='ssp' else self.scenario  
        tgt_rows=df_meta.loc[
            (df_meta['model_name'] == self.model_name) & (
            df_meta['scenario'] == meta_scenario)]
        if tgt_rows.shape[0] == 0:
            utils.throw_error(
                f'Error: Invalid scenario: {self.scenario} for model {self.model_name}')
        
        self.meta_rows=tgt_rows

        # build file names
        self.fn_lst=[]
        for idx, row in tgt_rows.iterrows():
            # get file name
            fn=row['naming_convention'].replace('SCENARIO',self.scenario)
            fn=fn.replace('YYYY',self.etl_strt_time.strftime('%Y'))
            fn=fn.replace('MM',self.etl_strt_time.strftime('%m'))
            self.fn_lst.append(self.in_root+'/'+fn)
            # get atm_frq
            if '*' in row['var_frq']:
                frq=row['var_frq'].replace('*','')
                self.out_time_series=pd.date_range(
                    start=self.etl_strt_time, end=self.etl_end_time, freq=frq)
    
    def _load_cmip_data(self):
        '''
        Load CMIP data according to file convension
        ''' 

        # init empty cmip container dict
        self.ds, self.outfrm={},{}
        
        for idx, irow in self.meta_rows.iterrows():
            vtable_fn=f"{self.model_name}_{irow['variable_group']}"
            df_vtable=pd.read_csv('./db/'+vtable_fn+'.csv')
            if self.model_name=='BCMM':
                ds=xr.open_dataset(self.fn_lst[idx])
                utils.write_log(print_prefix+'Loading '+self.fn_lst[idx])
            for idy, itm in df_vtable.iterrows():
                varname=itm['src_v']
                lvlmark=itm['lvlmark']
                if lvlmark == 'None':
                    lvlmark=''
                if varname in self.ds:
                    continue

                if not(self.model_name=='BCMM'):
                    pass

                # need interpolation coefficients
                if (lvlmark=='Lev' and itm['type']=='3d'):
                    if not(hasattr(self,'ap')):
                        self.ap=ds['ap'].values
                        self.b=ds['b'].values
                        self.ps=ds['ps'].sel(
                        time=slice(self.etl_strt_time,self.etl_end_time))

                # special for BCMM
                if (self.model_name=='BCMM' and irow['var_frq'] =='1M'): 
                    self.ds[varname]=ds[varname]
                else:
                    self.ds[varname]=ds[varname].sel(
                        time=slice(self.etl_strt_time,self.etl_end_time))
                
                # unify vertical layers naming 
                if (lvlmark=='PlevPt' and itm['type']=='3d'):
                    if 'lev' in self.ds[varname].coords:
                        self.ds[varname] = self.ds[varname].rename({'lev': 'plev'})
            ds.close()

    def parse_data(self, tf):
        '''
        data parser before write to WRF-Interim, including but not limited to:
            1. Interpolating to common mesh
            2. Dealing with missing values
            3. Converting Units 
        '''
        for idx, irow in self.meta_rows.iterrows():
            
            vtable_fn=f"{self.model_name}_{irow['variable_group']}"
            df_vtable=pd.read_csv('./db/'+vtable_fn+'.csv')
            
            for idy, itm in df_vtable.iterrows():
                varname=itm['src_v']
                lvltype=itm['type']
                lvlmark=itm['lvlmark']
                utils.write_log(
                    print_prefix+'Parsing '+varname+',lvltype='+lvltype+',lvlmark='+lvlmark)
                
                # special for BCMM
                if (self.model_name=='BCMM' and irow['var_frq'] =='1M'): 
                    da=self.ds[varname]
                else:
                    da=self.ds[varname].sel(time=tf, method='nearest')
                
                # units conversion, if necessary
                if varname =='mrsos' and itm['units']=='kg/m-3':
                    da.values=da.values*1e-2 # m^3/m-3
                if varname =='tos' and itm['units']=='degC':
                    da.values=da.values+273.15
                    itm['units']='K'

                if lvltype=='3d':
                    if lvlmark == 'Lev':
                        # interpolate from hybrid to pressure level 
                        da=utils.hybrid2pressure(
                            da,self.ap,self.b,self.ps.sel(time=tf, method='nearest'))
                    self.outfrm[varname]=da.interp(lat=utils.LATS, lon=utils.LONS, plev=utils.PLVS,
                            method='linear',kwargs={"fill_value": "extrapolate"})
               
                elif lvltype in ['2d', '2d-soil']:
                    da=da.interpolate_na(
                        dim="lon", method="linear",fill_value="extrapolate")    
                    self.outfrm[varname]=da.interp(lat=utils.LATS, lon=utils.LONS,
                        method='linear',kwargs={"fill_value": "extrapolate"})
 
                elif lvltype=='ocn2d':
                    ocn_da=da.interpolate_na(dim='i',
                        method='linear',fill_value="extrapolate")
                    ocn_da=ocn_da.interpolate_na(dim='j',
                        method='linear',fill_value="extrapolate")
                    grid_x,grid_y=np.meshgrid(new_lon,new_lat)
                    values=ocn_da.values
                    points=np.array(
                        [da.longitude.values.flatten(),da.latitude.values.flatten()]).T
                    # here use nearest as linear will cause some nan
                    grid_z0 = griddata(
                        points, values.flatten(), 
                        (grid_x, grid_y), method='nearest')  
                    self.outfrm[varname]=grid_z0
    
    def write_wrfinterm(self, tf, tgt):
        if tgt=='main':
            out_fn=self.out_root+'/'+self.model_name+':'+tf.strftime('%Y-%m-%d_%H')
        if tgt=='sst':
            out_fn=self.out_root+'/'+self.model_name+'_SST:'+tf.strftime('%Y-%m-%d_%H')
        
        utils.write_log(print_prefix+'Writing '+out_fn)
        # dtype='>u4' for header (big-endian, unsigned int)
        wrf_mid = FortranFile(out_fn, 'w', header_dtype=np.dtype('>u4'))
        
        out_dic=self.out_slab
        out_dic['HDATE']=tf.strftime('%Y-%m-%d_%H:%M:%S:0000')
        
        for idx, irow in self.meta_rows.iterrows():
            
            vtable_fn=f"{self.model_name}_{irow['variable_group']}"
            df_vtable=pd.read_csv('./db/'+vtable_fn+'.csv')
            
            for idy, itm in df_vtable.iterrows():
                if (tgt == 'sst' and itm['aim_v'] != 'SST'):
                    continue
                varname=itm['src_v']
                lvltype=itm['type']
                out_dic['FIELD']=itm['aim_v']
                out_dic['UNIT']=itm['units']
                out_dic['DESC']=itm['desc']
                out_dic['XLVL']=200100.0
                
                if varname=='tos':
                    out_dic['UNIT']='K'
                
                if lvltype=='3d':
                    for lvl in utils.PLVS:
                        out_dic['XLVL']=lvl
                        out_dic['SLAB']=self.outfrm[varname].sel(plev=lvl).values
                        utils.write_record(wrf_mid, out_dic)
                elif lvltype=='2d':
                    # use the lowest level if no direct output
                    #if varname=='tos':
                    #    out_dic['SLAB']=self.outfrm[varname]
                    if varname in ['ta', 'ua', 'va', 'hur', 'hus']:
                        out_dic['SLAB']=self.outfrm[varname].sel(plev=100000.0).values
                    else: 
                        out_dic['SLAB']=self.outfrm[varname].values
                elif lvltype=='2d-soil':
                    index = next(
                        (i for i, s in enumerate(utils.SOIL_LVS) if s in itm['aim_v']), None)
                    out_dic['SLAB']=self.outfrm[varname].values[:,index,:,:]
                utils.write_record(wrf_mid, out_dic)
        wrf_mid.close()


if __name__ == "__main__":
    pass
