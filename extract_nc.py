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
 
    strt_time=datetime.datetime.strptime('2045-01-01 06:00','%Y-%m-%d %H:%M')
    end_time=datetime.datetime.strptime('2045-01-01 12:00','%Y-%m-%d %H:%M')

    dt=datetime.timedelta(hours=6)

    fake_strt_time=datetime.datetime.strptime('2020-12-19_12','%Y-%m-%d_%H')
    fake_dt=datetime.timedelta(hours=3)

    #new_lat = np.linspace(-90, 90., 721)
    new_lat = np.linspace(-90, 90., 181)
    #new_lon = np.linspace(0., 359.75, 1440)
    new_lon = np.linspace(0., 359, 360)
    new_lv = 100.0*np.array([1000.0, 925.0, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50])
    #new_lv = 100.0*np.array([1000.0, 925.0, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50, 30, 20, 10])
    ''' GFS
    new_lv = np.array([100, 200.0, 300.0, 500.0, 700.0, 1000. ,1500,       2000,       3000,      4000,      5000,
              7000,      0.1000E+05,  0.1500E+05,  0.2000E+05,  0.2500E+05,  0.3000E+05,
                0.3500E+05,0.4000E+05,0.4500E+05,0.5000E+05,0.5500E+05,0.6000E+05,
                0.6500E+05,0.7000E+05,0.7500E+05,0.8000E+05,0.8500E+05,0.9000E+05,
                0.9250E+05,0.9500E+05,0.9750E+05,0.1000E+06])
    '''
    vtable=pd.read_csv('./db/vtable.min.csv')
    print('Construct CMIP Container...')
    print(vtable)
    for idx, itm in vtable.iterrows():
        if itm['src_v']=='orog' or itm['src_v']=='sftlf':
            continue
        cmip=lib.cmip_container.cmip_container(cfg_hdl,itm)
        print(cmip.fn)
        ds=cmip.ds
        curr_time=strt_time
        fake_curr_time=fake_strt_time
        while curr_time<=end_time:
            print(fake_curr_time.strftime('%Y-%m-%d_%H'))
            dsi=ds.sel(time=curr_time)
          
            if itm['type']=='3d':
                dsi=dsi.interp(lat=new_lat, lon=new_lon, plev=new_lv,
                        method='linear',kwargs={"fill_value": "extrapolate"})
            elif itm['type']=='2d':
                dsi=dsi.interp(lat=new_lat, lon=new_lon,
                        method='linear',kwargs={"fill_value": "extrapolate"})

            dsi.to_netcdf('./output/'+itm['src_v']+'_'+fake_curr_time.strftime('%Y-%m-%d_%H')+'.nc')
            fake_curr_time=fake_curr_time+fake_dt
            curr_time=curr_time+dt

if __name__=='__main__':
    main_run()
