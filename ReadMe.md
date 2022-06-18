# cmip6-to-wrfinterm

The repo uses fortran source files and python scripts to convert CMIP6 6-houly output into WRF middle files, which are used to drive WRF model.
The repo was only tested for MPI-ESM-1-2-HR model in SSP1/2/5 scenarios currently, you may need proper modifications for other model convension.

### Input Files

#### config.ini
`./conf/config.ini`: Configure file for the model.

#### build_wrfmid_with_soil.f90
Core middle file generator.

#### extract.py
Preprocessor, extract nc files for individual variables from raw CMIP6 output.

**Any question, please contact Zhenning LI (zhenningli91@gmail.com)**


