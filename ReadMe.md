
# cmip6-to-wrfinterm

The repo uses fortran and python scripts to convert CMIP6 6-hr/3-hr output into WRF middle files, which are used to drive WRF model.

### Input Files

#### config.ini
`./conf/config.ini`: Configure file for the model.

#### build_wrfmid_with_soil.f90
Core middle file generator.

#### extract.py
Preprocessor, extract nc files for individual variables from raw CMIP6 output.

**Any question, please contact Zhenning LI (zhenningli91@gmail.com)**


