# cmip6-to-wrfinterm

The repo uses fortran source files and python scripts to convert CMIP6 6-houly output into WRF intermediate files, which are used to drive WRF model.
Currently, the repo was only tested for **MPI-ESM-1-2-HR** model in **historical run and SSP1/2/5 scenarios**, you may need proper modifications for other model convension.

Here we give a SSP245 run for example to show the usage of this repo.


## Fetch Input Files

According to WRF Users Guide (v4.2), P3-36:
> **Required Meteorological Fields for Running WRF**
>> In order to successfully initialize a WRF simulation, the real.exe pre-processor requires a 
>> minimum set of meteorological and land-surface fields to be present in the output from 
>> the metgrid.exe program. Accordingly, these required fields must be available in the 
>> intermediate files processed by metgrid.exe. 



**Any question, please contact Zhenning LI (zhenningli91@gmail.com)**


