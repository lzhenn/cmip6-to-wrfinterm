#/usr/bin/env python
"""Time manager obj to record execution time."""

import time

class time_manager:
    '''
    Time manager object to record execution time
    
    Attributes
    -----------
    tic0, float, absolute start time of the program
    tic, float, absolute start time before each module in runtime
    record, list[i]=(evt_str, dt), runtime duration of each individual event 

    Methods
    -----------
    toc(evt_str), press toc after each event (evt_str)
    dump(), dump time manager object in output stream

    '''

    def __init__(self):
        """construct time manager object"""
        self.tic0=time.time()
        self.tic=self.tic0
        self.record=[]

    def toc(self, evt_str):
        """press toc after each event (evt_str)"""
        self.record.append((evt_str, time.time()-self.tic))
        self.tic=time.time()

    def dump(self):
        """Dump time manager object in output stream"""
        fmt='%20s:%10.4fs%6.1f%%'
        print('\n----------------TIME MANAGER PROFILE----------------\n\n')
        total_t=time.time()-self.tic0
        for rec in self.record:
            print(fmt % (rec[0],rec[1],100.0*rec[1]/total_t))
        print(fmt % ('TOTAL ELAPSED TIME', total_t, 100.0))
        print('\n----------------TIME MANAGER PROFILE----------------\n\n')
