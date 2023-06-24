#/usr/bin/env python3
'''
Date: Feb 25, 2021

This is the main script to drive the CMIP6-WRF data extraction. 

Revision:
Jul  3, 2022 --- Revised for NCL version 
Feb 25, 2021 --- MVP v0.01 completed

Zhenning LI
'''
import lib
import logging, logging.config
from utils import utils
import argparse
import os





def main_run():

    # logging manager
    logging.config.fileConfig('./conf/logging_config.ini')
    

    parser = argparse.ArgumentParser(
        description='Process some user inputs.')
    parser.add_argument(
        '-m', '--model_name', type=str, 
        default='MPI-ESM1-2-HR', help='Model name for config file path')
    args = parser.parse_args()

    config_file_path = f'./conf/config.{args.model_name}.ini'

    if not os.path.exists(config_file_path):
        utils.throw_error(
            f'Error: Invalid input model_name "{args.model_name}"')
        exit()

    utils.write_log(f'Read Config for {args.model_name}...')
    
    cfg_hdl=lib.cfgparser.read_cfg(config_file_path)
 
    utils.write_log('Construct CMIPHandler...')
    cmip_hdl=lib.cmip_handler.CMIPHandler(cfg_hdl)

    for time_frm in cmip_hdl.out_time_series:
        utils.write_log('Processing time: '+str(time_frm))
        cmip_hdl.parse_data(time_frm)
        utils.write_log('Writing time: '+str(time_frm))
        cmip_hdl.write_wrfinterm(time_frm, 'main')
        cmip_hdl.write_wrfinterm(time_frm, 'sst')
    
if __name__=='__main__':
    main_run()
