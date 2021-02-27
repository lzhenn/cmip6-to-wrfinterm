#/usr/bin/env python3
"""Build Observation Station Objects"""

import datetime
import pandas as pd 
import numpy as np
import xarray as xr

import sys
sys.path.append('../')
from utils import utils


print_prefix='lib.cmip_container>>'

class cmip_container:

    '''
    Construct CMIP Container 

    Attributes
    -----------

    Methods
    -----------

    '''
    
    def __init__(self, cfg, var_dic):
        """ construct obv obj """
        in_cfg=cfg['INPUT']
        varname=var_dic['src_v']
        lvlmark=var_dic['lvlmark']
        #ts_6hrPlevPt_MPI-ESM1-2-HR_ssp585_r1i1p1f1_gn_204001010600-204501010000.nc
        self.fn=in_cfg['input_root']+varname+'_'+in_cfg['input_frq']+lvlmark+'_'+in_cfg['model_name']
        self.fn=self.fn+'_'+in_cfg['exp_id']+'_'+in_cfg['esm_flag']+'_'+in_cfg['grid_flag']
        self.fn+='_'+in_cfg['model_strt_ts']+'-'+in_cfg['model_end_ts']+'.nc'
        self.ds=xr.open_dataset(self.fn)
        

    def dump(self, wind_prof_df):
        """ search wind profile pvalue in table """

        x_org=wind_prof_df['roughness_length'].values
        y_org=wind_prof_df[self.stab_lvl].values
        interp=interpolate.interp1d(x_org,y_org)
        self.prof_pvalue=interp(self.rough_len)
                
    def get_in_situ_prof(self, fields_hdl):
        """ get in-situ wind profile in the observation station """
        
        # get the wind profile from template file
        (idx,idy)=utils.get_closest_idxy(fields_hdl.XLAT_U.values,fields_hdl.XLONG_U.values,self.lat,self.lon)
        self.u_prof=fields_hdl.U.values[:,idx,idy]
        (idx,idy)=utils.get_closest_idxy(fields_hdl.XLAT_V.values,fields_hdl.XLONG_V.values,self.lat,self.lon)
        self.v_prof=fields_hdl.V.values[:,idx,idy]

        # power law within near surf layer 
        idz=fields_hdl.near_surf_z_idx+1
        self.u_prof[0:idz]=[utils.wind_prof(self.u0, self.z, z, self.prof_pvalue) for z in fields_hdl.z[0:idz].values]
        self.v_prof[0:idz]=[utils.wind_prof(self.u0, self.z, z, self.prof_pvalue) for z in fields_hdl.z[0:idz].values]
        
        # Ekman layer, interpolate to geostrophic wind
        idz2=fields_hdl.geo_z_idx+1
        
        x_org=[fields_hdl.z[idz-1], fields_hdl.z[idz2]]
        u_org=[self.u_prof[idz-1], self.u_prof[idz2]]
        v_org=[self.v_prof[idz-1], self.v_prof[idz2]]
        interp_u=interpolate.interp1d(x_org,u_org)
        interp_v=interpolate.interp1d(x_org,v_org)

        self.u_prof[idz:idz2]=geo_u=interp_u(fields_hdl.z.values[idz:idz2])
        self.v_prof[idz:idz2]=geo_u=interp_v(fields_hdl.z.values[idz:idz2])

if __name__ == "__main__":
    pass
