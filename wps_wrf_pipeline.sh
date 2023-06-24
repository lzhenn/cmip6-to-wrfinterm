# Set up Constants
date

OUT_DIR=`pwd`/output/
MODEL_NAME=BCMM
SAMPLE_DIR=`pwd`/sample/$MODEL_NAME/

WPS_DIR=/home/lzhenn/WRFv43-preprocess/WPS-4.3/
WRF_DIR=/home/lzhenn/WRFv43-preprocess/WRF-4.3//run

WPS_FLAG=1
REAL_FLAG=1
WRF_FLAG=1

NTASKS=32
#-----------------WPS---------------------
if [ $WPS_FLAG == 1 ]; then
    LOGFILE=wps.log
    echo ">>>>WRF-WPS"
    cd $WPS_DIR

    # Clean WPS data
    #rm -f geo_em*
    echo ">>>>WRF-WPS:Clean Pre-existed Files..."
    rm -f met_em.*
    rm -f GFS:*
    rm -f ERA*
    rm -f CMIP*
    rm -f SST:*
    rm -f $MODEL_NAME*
    cp $SAMPLE_DIR/namelist.wps ./
    ln -sf $OUT_DIR/$MODEL_NAME* ./
    echo ">>>>WRF-WPS:geogrid..."
    #./geogrid.exe
    

    echo ">>>>WRF-WPS:Working on WPS->Metgrid..."
    mpirun -np 8 ./metgrid.exe >& $LOGFILE
fi
date

#-----------------REAL---------------------
if [ $REAL_FLAG == 1 ]; then
    echo ">>>>WRF-REAL:Clean Pre-existed Files..."
    cd $WRF_DIR
    cp ${SAMPLE_DIR}/namelist.input $WRF_DIR

    rm -f met_em.d0*
    rm -f wrfinput_d0*
    rm -f wrflowinp_d0*
    rm -f wrfbdy_d0*
    rm -f wrffda*

    echo ">>>>WRF-REAL: Run real.exe..."
    ln -sf $WPS_DIR/met_em.d0* ./
    mpirun -np 16 ./real.exe
fi
date
#-----------------WRF---------------------
if [ $WRF_FLAG == 1 ]; then
    echo ">>>>WRF-WRF: Run wrf.exe..."
    cd $WRF_DIR
    mpirun -np  $NTASKS ./wrf.exe
fi
echo ">>>>ALL DONE!!!"
date