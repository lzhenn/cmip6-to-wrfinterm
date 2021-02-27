WPSDIR=/home/metctm1/array/app/WPS
ifort -I/home/metctm1/array/soft/netcdf-474c453f-intel20/include -convert big_endian build_wrfmid.f90 -L/home/metctm1/array/soft/netcdf-474c453f-intel20/lib -lnetcdf -lnetcdff
#pgf90 -I/home/metctm1/array/soft/netcdf-474c453f-pgi20/include -byteswapio test_sst.f90 -L/home/metctm1/array/soft/netcdf-474c453f-pgi20/lib -lnetcdf -lnetcdff
./a.out
cp CMIP:2020-12-19_12 $WPSDIR
cd $WPSDIR
./metgrid.exe
