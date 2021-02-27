;-----------------------------------------------------------------
; Convert FNL GRIB2 data to GRAPES TRAMS input data.
;
; Concepts illustrated:
; USing fbinrecwrite() to write multiple variables to an sequential binary file.
;-----------------------------------------------------------------

load "$NCARG_ROOT/lib/ncarg/nclscripts/csm/gsn_code.ncl"
load "$NCARG_ROOT/lib/ncarg/nclscripts/csm/gsn_csm.ncl"
load "$NCARG_ROOT/lib/ncarg/nclscripts/csm/contributed.ncl"

load "$NCARG_ROOT/lib/ncarg/nclscripts/contrib/cd_string.ncl"


begin
    ; define environment variables
    ; FNL path
    fnl_path = "/mnt/hgfs/VMshare/1/"
    ; GRAPES output path
    grapes_path = "/mnt/hgfs/VMshare/grapes-data/"
    system("rm -rf "+grapes_path)
    system("mkdir "+grapes_path)

    ; Set time for the FNL data
    Stime = "2017-08-19 12:00:00"
    Etime = "2017-08-24 12:00:00"
    ; Set layers for grapes data
    z_lays = (/1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50, 30, 20, 10/)
    z_lays = z_lays*100

    ; 3D varlist
    varlist3d = (/"TMP", "HGT", "UGRD", "VGRD", "RH"/)
    varlist3d = varlist3d+"_P0_L100_GLL0"
    num_var3d = dimsizes(varlist3d)

    ; 2D varlist
    varlist2d = (/"PRES", "TMP"/)
    varlist2d = varlist2d+"_P0_L1_GLL0"
    num_var2d = dimsizes(varlist2d)


    time0 = 0
    time0@units = "hours since " + Stime
    cd_time0 = cd_calendar(time0, 3)

    tt = time0

    timeN = 0
    timeN@units = "hours since " + Etime
    cd_timeN = cd_calendar(timeN, 3)


    pre3d = conform_dims((/14,181,360/), z_lays(0:13)/100, 0)
    n_file = 0

    do while (cd_time0 .lt. cd_timeN)

        cd_time0 = cd_calendar(time0, 3)
        time0_str = cd_string(time0, "%Y%N%D_%H_%M")

        ; READ the FNL GRIB2 variables and output into binary
        ;grib_in = addfile(fnl_path+"fnl_"+time0_str+".grib2", "r")
        fi = addfile(fnl_path+"fnl_"+time0_str+".grib2", "r")

        ;;convert GRIB2 data to NC data
        ;print("Now convert GRIB2 data ("+"fnl_"+time0_str+".grib2"+") to NC.")
        ;names = getfilevarnames(grib_in)
        ;system("rm -rf "+fnl_path+"fnl_"+time0_str+".nc")
        ;ncdf_out = addfile(fnl_path+"fnl_"+time0_str+".nc" ,"c")
        ;do i = 0, dimsizes(names)-1
        ;    ncdf_out->$names(i)$ = grib_in->$names(i)$
        ;end do
        ;delete([/grib_in, names, ncdf_out/])

        ;fi = addfile(fnl_path+"fnl_"+time0_str+".nc" ,"r")

        ;fo_path = grapes_path+"GFP"+cd_string(time0, "%Y%N%D%H")+sprinti("%0.3i", n_file*6)
        fo_path = grapes_path+"GFP"+cd_string(tt, "%Y%N%D%H")+sprinti("%0.3i", n_file*6)
        print(fo_path+" is processing ...")
        system("rm -rf "+fo_path)
        setfileoption("bin","WriteByteOrder","BigEndian")


        do ii = 0, num_var3d-1, 1  ;do not write out the RH data first
            var3d     :=  fi->$varlist3d(ii)$
            var3d_slc :=  var3d({z_lays},::-1,:)
            if (ii.ne.num_var3d-1) then
                if (ii.eq.0) then
                    t3d := var3d_slc
                end if
                ;printVarSummary(var3d_slc)
                do jj = 0, dimsizes(z_lays)-1, 1
                    fbinrecwrite(fo_path, -1, (/var3d_slc(jj,:,:)/))
                end do
            else
                rh3d := var3d_slc
            end if
        end do

        ; convert relative humidity to specific humidity
        QV := mixhum_ptrh(pre3d, t3d(0:13,:,:), rh3d(0:13,:,:), 2)
        do i = 0, 1, 1
            do jj = 0, 14-1, 1
                fbinrecwrite(fo_path, -1, (/QV(jj,:,:)/))
            end do
        end do

        do ii = 0, num_var2d-1,1
            var2d     := fi->$varlist2d(ii)$
            var2d_slc := var2d(::-1,:)
            ;printVarSummary(var2d_slc)
            if (ii.eq.0) then
                ; surface pressure (hPa)
                fbinrecwrite(fo_path, -1, (/var2d_slc/100.0/))
            elseif (ii.eq.1) then
                ; surface temperature (K)
                fbinrecwrite(fo_path, -1, (/var2d_slc/))
            end if

        end do

        time0 = time0 + 6
        n_file = n_file + 1

    end do


end