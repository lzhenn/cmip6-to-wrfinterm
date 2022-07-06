# cmip6-to-wrfinterm

**CMIP6-to-WRFInterim** uses pure python implementation to convert CMIP6 sub-daily output into WRF intermediate files, which are used to drive the WRF model for regional dynamical downscaling usage.
Currently, only **MPI-ESM-1-2-HR** model has been teseted in **historical run and SSP1/2/5 scenarios**, you may need proper modifications for other model convension.

## Installation
Please install python3 using Anaconda3 distribution. [Anaconda3](https://www.anaconda.com/products/individual) with python3.8 and 3.9 has been deeply tested, lower version of python3 may also work (without testing). If `numpy`, `pandas`, `scipy`, `xarray`, `netcdf4` are properly installed, you may skip the installation step.

While, we recommend to create a new environment in Anaconda and install the `requirements.txt`:

```bash
conda create -n test_c2w python=3.9
conda activate test_c2w
pip install -r requirements.txt
```

## Quick start

'''bash
python3 run_c2w.py
'''

If you successfully run the above command (it is okay to see some FutureWarnings), you should see `CMIP6:2100-01-02_00` and `CMIP6:2100-01-02_00` in the `./output` folder. 
Copy or link the two intermidiate files to your WPS folder, prepare your **geo_em** files and setup your `namelist.wps` properly, now you are ready to run `metgrid.exe` and the following WRF procedures.

There is a simple example of `namelist.wps` and `namelist.input` covering the East Asian region in the `./sample` folder for testing.

A snapshot of the skin temperature in the initial condition and after 6-hour WRFv4.3 run is shown below.


## Usage

### ./conf/config.ini

When you properly download the CMIP6 data, First edit the `./conf/config.ini` file properly.

``` python
[INPUT]
input_root=./sample/ 
model_name=MPI-ESM1-2-HR
exp_id = ssp585
esm_flag=r1i1p1f1
grid_flag=gn
#YYYYMMDDHHMM
cmip_strt_ts = 210001020000
cmip_end_ts = 210001020600
# In hours
cmip_frq=6

[OUTPUT]
#YYYYMMDDHHMM, please seperate your ETL processes if request very long-term simulation
etl_strt_ts = 210001020000
etl_end_ts = 210001020600
output_root = ./output/
output_prefix=CMIP6 
``` 
* [INPUT]['input_root'] is the root directory of the CMIP6 data, here it points to the `./sample/` folder.
* [INPUT]['model_name'] is the name of the model. Now only the `MPI-ESM-1-2-HR` model is supported. This item will guide the script to read the corresponding variable mapping table in `./db/`. If you plan to use other models, you need to setup your own variable mapping table.ls
* [INPUT]['exp_id'] ['esm_flag'] ['grid_flag'] are used to form the netCDF file name.
* [INPUT]['cmip_strt_ts'] and [INPUT]['cmip_end_ts'] are the start and end time of the CMIP6 data.

### 



## Fetch Input Files

According to WRF Users Guide (v4.2), P3-36:
> **Required Meteorological Fields for Running WRF**
>> In order to successfully initialize a WRF simulation, the real.exe pre-processor requires a 
>> minimum set of meteorological and land-surface fields to be present in the output from 
>> the metgrid.exe program. Accordingly, these required fields must be available in the 
>> intermediate files processed by metgrid.exe. 

CMIP6 data can be downloaded from the [LLNL interface](https://esgf-node.llnl.gov/search/cmip6/), after cross-check the variable list from **MPI-ESM-1-2-HR** and teh WRF required variables,
we have the following table:
![](https://raw.githubusercontent.com/Novarizark/cmip6-to-wrfinterm/master/fig/var_table.png)


**Any question, please contact Zhenning LI (zhenningli91@gmail.com)**


