#/usr/bin/env python3
'''
Date: Feb 25, 2021

This is the main script to drive the CMIP6-WRF data extraction. 

Revision:
Jul  3, 2022 --- Revised for NCL version 
Feb 25, 2021 --- MVP v0.01 completed

Zhenning LI
'''
import numpy as np
import pandas as pd
import datetime
import lib
import logging, logging.config
from utils import utils




def main_run():

    # logging manager
    logging.config.fileConfig('./conf/logging_config.ini')
    

    utils.write_log('Read Config...')
    cfg_hdl=lib.cfgparser.read_cfg('./conf/config.ini')
 
    utils.write_log('Construct CMIPHandler...')
    cmip_hdl=lib.cmip_handler.CMIPHandler(cfg_hdl)

    for time_frm in cmip_hdl.out_time_series:
        utils.write_log('Processing time: '+str(time_frm))
        cmip_hdl.interp_data(time_frm)
        utils.write_log('Writing time: '+str(time_frm))
        cmip_hdl.write_wrfinterm(time_frm)
    
if __name__=='__main__':
    main_run()
