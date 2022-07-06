#/usr/bin/env python
"""Commonly used utilities"""
import logging

def throw_error(msg):
    '''
    throw error and exit
    '''
    logging.error(msg)
    logging.error('Abnormal termination of Easy ERA5 Trac!')

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
