#/usr/bin/env python3
'''
Date: Feb 25, 2021

This is the main script to drive the model

Revision:
Feb 25, 2021 --- MVP v0.01 completed

Zhenning LI
'''
import numpy as np
import pandas as pd
import xarray as xr
import datetime
import lib

def main_run():
    
    print('Read Config...')
    cfg_hdl=lib.cfgparser.read_cfg('./conf/config.ini')
 
    etl_strt_time=datetime.datetime.strptime(cfg_hdl['CORE']['etl_strt_ts'],'%Y%m%d%H%M')
    etl_end_time=datetime.datetime.strptime(cfg_hdl['CORE']['etl_end_ts'],'%Y%m%d%H%M')
    dt=datetime.timedelta(hours=6)

    time_series=pd.date_range(start=etl_strt_time, end=etl_end_time, freq=dt)

    #new_lat = np.linspace(-90, 90., 721)
    new_lat = np.linspace(-90, 90., 181)
    #new_lon = np.linspace(0., 359.75, 1440)
    new_lon = np.linspace(0., 359, 360)
    new_lv = 100.0*np.array([1000.0, 925.0, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50])
    #new_lv = 100.0*np.array([1000.0, 925.0, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50, 30, 20, 10])
    vtable=pd.read_csv('./db/vtable.min.csv')
    
    print('Construct CMIP Container...')
    print(vtable)
    for idx, itm in vtable.iterrows():
        # exceptions
        if itm['src_v']=='orog' or itm['src_v']=='sftlf':
            continue
        
        cmip=lib.cmip_container.cmip_container(cfg_hdl,itm)
        ds=cmip.ds
        curr_time=etl_strt_time
        while curr_time<=etl_end_time:
            curr_timestamp=curr_time.strftime('%Y-%m-%d_%H')
            dsi=ds.sel(time=curr_time)
          
            if itm['src_v'] =='mrsos':
                dsi['mrsos'].values=dsi['mrsos'].values*1e-2

            if itm['type']=='3d':
                dsi=dsi.interp(lat=new_lat, lon=new_lon, plev=new_lv,
                        method='linear',kwargs={"fill_value": "extrapolate"})
            elif itm['type']=='2d':
                dsi=dsi.interp(lat=new_lat, lon=new_lon,
                        method='linear',kwargs={"fill_value": "extrapolate"})
            elif itm['type']=='2d-soil':
                dsi=dsi.interpolate_na(dim="lon", method="linear",fill_value="extrapolate")
                dsi=dsi.interp(lat=new_lat, lon=new_lon,
                        method='linear',kwargs={"fill_value": "extrapolate"})
            out_fn=cfg_hdl['OUTPUT']['output_root']+cfg_hdl['INPUT']['exp_id']+'/'+itm['src_v']+'_'+curr_timestamp+'.nc'
            print(out_fn)            
            dsi.to_netcdf(out_fn)
            curr_time=curr_time+dt

    with open(cfg_hdl['OUTPUT']['output_root']+cfg_hdl['INPUT']['exp_id']+'/timelist', 'a') as f:
        for itime in time_series:
            f.write(itime.strftime('%Y-%m-%d_%H')+'\n')

if __name__=='__main__':
    main_run()
