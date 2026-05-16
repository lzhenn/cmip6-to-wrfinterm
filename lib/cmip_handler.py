#/usr/bin/env python3
"""Build Observation Station Objects"""

import glob
import json
import os
import datetime
import pandas as pd
import xarray as xr
import numpy as np
from scipy.io import FortranFile
from utils import utils
from utils.grid import OutputGrid
from utils import soil as soil_utils
from lib.adapters import make_adapter, CFTIME_MODELS  # CFTIME_MODELS re-exported for any external caller


print_prefix='lib.cmip_handler>>'

# Vtable type taxonomy. These constants stay in the handler because they
# describe the *semantics* the handler dispatches on, not per-model layout.
SOIL_MON_TYPES = {'2d-soil-mon', '2d-soilr-mon'}      # monthly soil → snap to month, used for init
TIMEDEP_2D_TYPES = {'2d-daily', '2d-mon'}             # daily/monthly 2D (tos, ts) → nearest in time
FIXED_2D_TYPES = {'2d-fixed'}                          # time-invariant (orog, sftlf)
# All soil-typed vtable rows. Used by the soil_strategy='skip' early-exit
# so the handler treats them uniformly regardless of -mon / -r variants.
SOIL_ALL_TYPES = {'2d-soil', '2d-soilr', '2d-soil-mon', '2d-soilr-mon'}


class CMIPHandler(object):

    '''
    Construct CMIP Handler

    Methods
    -----------
    __init__:   initialize CMIP Handler with config and loading data
    interp_data: interpolate data to common mesh
    write_wrfinterm: write wrfinterm file

    '''

    def __init__(self, cfg):
        '''
        Initialize CMIP Handler with config and load data
        '''

        in_cfg=cfg['INPUT']
        out_cfg=cfg['OUTPUT']

        self.model_name=in_cfg['model_name']
        # `scenario` is the canonical key; some legacy configs (EC-Earth3)
        # use `exp_id` instead. Accept either so EC-Earth3 keeps working
        # without an ini-file migration.
        if 'scenario' in in_cfg:
            self.scenario=in_cfg['scenario']
        elif 'exp_id' in in_cfg:
            self.scenario=in_cfg['exp_id']
        else:
            utils.throw_error(
                f'No "scenario" (or legacy "exp_id") key in [INPUT] section '
                f'of config for model {self.model_name}.')

        self.etl_strt_time=datetime.datetime.strptime(
            out_cfg['etl_strt_ts'],'%Y%m%d%H%M')
        self.etl_end_time=datetime.datetime.strptime(
            out_cfg['etl_end_ts'],'%Y%m%d%H%M')
        self.in_root=in_cfg['input_root']
        self.out_root=out_cfg['output_root']

        # cache: group_name -> stripped vtable DataFrame (read once)
        self.vtables={}
        # depth_bnds (Nsoil, 2) captured from each multi-layer soil source,
        # keyed by src_v. Read in _load_cmip_data, consumed by parse_data
        # for the overlap-weighted soil remap.
        self.soil_depth_bnds={}

        # Output grid: lat/lon mesh, pressure levels, soil layers. Comes from
        # the [OUTPUT] section; absent keys fall back to historical defaults
        # (1deg global, 14 plev, 4 soil layers), so legacy configs work as-is.
        self.grid = OutputGrid.from_config(out_cfg)
        utils.write_log(f'{print_prefix}{self.grid}')

        # Adapter owns model-specific file discovery, ds opening, calendar.
        self.adapter = make_adapter(
            in_cfg, self.scenario, self.etl_strt_time, self.etl_end_time)
        self.use_cftime = self.adapter.use_cftime  # backwards-compat alias

        # Soil "init-only" optimization (default ON). WRF's LSM only consumes
        # soil at t=0 (it then evolves the field prognostically), but
        # real.exe v4.3 does a structural-consistency check on every met_em
        # file it reads and would FATAL if later files lacked soil records.
        #
        # We split the difference: cache the t=0 soil result in self.outfrm
        # and reuse the same slab for every subsequent wrfinterm. real.exe
        # sees the records it wants at every time; the LSM math is identical
        # (it only initialised from t=0); and we skip the relatively
        # expensive parse step (depth remap, land-fill, regrid) for tf>t0.
        #
        # Set [OUTPUT] soil_init_only = false to recompute soil per time —
        # useful only if you're doing something like soil-moisture nudging
        # downstream that actually inspects later met_em soil records.
        _siok = str(out_cfg.get('soil_init_only', 'true')).strip().lower()
        self.soil_init_only = _siok in ('1', 'true', 'yes', 'on')

        self._build_meta(in_cfg)
        # First time slice in the output cadence; soil records only get
        # produced/written at this timestamp when soil_init_only is on.
        self._soil_first_tf = self.out_time_series[0]
        self._load_cmip_data()
        self.out_slab=utils.gen_wrf_mid_template(self.grid)
        self._emit_namelist_hints()

    def _load_vtable(self, group_name):
        '''Read & cache a vtable. String columns get whitespace-stripped once
        on load so downstream comparisons don\'t need ad-hoc .strip().'''
        if group_name in self.vtables:
            return self.vtables[group_name]
        df = pd.read_csv(f"./db/{self.model_name}_{group_name}.csv")
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].astype(str).str.strip()
        self.vtables[group_name] = df
        return df

    def _build_meta(self, in_cfg):
        '''Filter meta CSV down to rows for the active (model, scenario) and
        derive the output time series from whichever row carries the `*`
        flag in `var_frq` (the master cadence).
        '''
        df_meta=pd.read_csv('./db/cmip6_meta.csv')
        meta_scenario='ssp' if self.scenario[0:3]=='ssp' else self.scenario
        tgt_rows=df_meta.loc[
            (df_meta['model_name'] == self.model_name) & (
            df_meta['scenario'] == meta_scenario)]
        if tgt_rows.shape[0] == 0:
            avail = sorted(set(df_meta.loc[
                df_meta['model_name']==self.model_name, 'scenario']))
            utils.throw_error(
                f'Invalid scenario "{self.scenario}" for model '
                f'"{self.model_name}". Available scenarios in meta: {avail}')

        self.meta_rows=tgt_rows

        for _, row in tgt_rows.iterrows():
            if '*' in str(row['var_frq']):
                master_frq = str(row['var_frq']).replace('*', '')
                self.out_time_series = pd.date_range(
                    start=self.etl_strt_time, end=self.etl_end_time,
                    freq=master_frq)
                break
        if not hasattr(self, 'out_time_series'):
            utils.throw_error(
                f'No row marked with "*" in var_frq for '
                f'{self.model_name}/{self.scenario}; '
                f'cannot determine master output cadence.')

    def _extract_hybrid_coeffs(self, ds):
        '''Pull (ap, b, optionally ps) for hybrid-sigma → pressure conversion.

        Called from the *first* 3D Lev variable encountered. ap may live as
        `ap` directly or be reconstructed from `a * p0`. ps is taken from
        the same file when present (MPI); otherwise it is filled in later
        from the standalone `ps` variable file (CESM2).'''
        if 'ap' in ds:
            self.ap = ds['ap'].values
        elif 'a' in ds and 'p0' in ds:
            self.ap = (ds['a'] * float(ds['p0'])).values
        else:
            utils.throw_error(
                'Cannot find hybrid coefficients (ap or a+p0) in dataset')
        self.b = ds['b'].values
        if 'ps' in ds:
            self.ps = ds['ps'].sel(time=slice(
                self.etl_strt_time.strftime('%Y-%m-%d'),
                self.etl_end_time.strftime('%Y-%m-%d')))

    def _load_sftlf_helper(self):
        '''Optional land-area-fraction mask used by `_fill_2d` to keep
        nearest-neighbour fills from crossing the coastline. Skipped when
        no `sftlf_*.nc` is present.'''
        matches = sorted(glob.glob(f"{self.in_root.rstrip('/')}/sftlf_*.nc"))
        if not matches:
            return
        sf = xr.open_dataset(matches[0])
        self.sftlf = sf['sftlf'].values.astype(np.float32)
        utils.write_log(
            f'{print_prefix}Loaded sftlf helper from {matches[0]} '
            f'(shape={self.sftlf.shape})')
        sf.close()

    def _emit_namelist_hints(self):
        '''When the adapter declined to write soil records, drop a sidecar
        JSON in `out_root` so the run script can patch the WRF namelist
        accordingly. No-op when soil_strategy == 'native'.
        '''
        if self.adapter.soil_strategy != 'skip':
            return
        os.makedirs(self.out_root, exist_ok=True)
        path = os.path.join(
            self.out_root, f'{self.model_name}.namelist_hints.json')
        hints = {
            'num_metgrid_soil_levels': 0,
            'surface_input_source':    2,
            '_reason': (
                f'{self.model_name} publishes only surface-level soil data '
                f'(no usable deep profile). c2w skipped soil records; these '
                f'overrides tell real.exe to interpolate soil temperature '
                f'from the atmospheric column instead of expecting fabricated '
                f'deep layers in the wrfinterm files.'),
            '_apply_to': 'namelist.input',
        }
        with open(path, 'w') as f:
            json.dump(hints, f, indent=2)
        utils.write_log(
            f'{print_prefix}Wrote namelist hints → {path} '
            f'(set num_metgrid_soil_levels=0 + surface_input_source=2 '
            f'in your namelist.input before real.exe)')

    def _load_cmip_data(self):
        '''Load every variable declared by the active meta + vtable rows.

        File discovery, dataset opening and calendar handling are owned by
        `self.adapter`. The handler stays focused on the *semantic* layer:
        time slicing, hybrid-coord setup, lev-orientation alignment, and
        coord-name normalization.
        '''
        self.ds, self.outfrm = {}, {}

        for _, group_row in self.meta_rows.iterrows():
            df_vtable = self._load_vtable(group_row['variable_group'])
            for _, vtable_row in df_vtable.iterrows():
                varname = vtable_row['src_v']
                lvltype = str(vtable_row['type'])
                lvlmark = vtable_row.get('lvlmark', '')
                if pd.isna(lvlmark) or str(lvlmark) == 'None':
                    lvlmark = ''
                else:
                    lvlmark = str(lvlmark)

                # Repeated src_v across vtable rows (e.g. tsl × 4 soil layers
                # in CESM2_Lmon) — load once.
                if varname in self.ds:
                    continue

                # Honor soil_strategy='skip': don't even open the dataset.
                # The model's published soil profile is surface-only, so any
                # deep-layer record we'd produce would be a fabrication.
                # Downstream WRF will use surface_input_source=2 instead.
                if (lvltype in SOIL_ALL_TYPES
                        and self.adapter.soil_strategy == 'skip'):
                    utils.write_log(
                        f'{print_prefix}Skipping soil var {varname} '
                        f'(adapter soil_strategy=skip; WRF will interpolate '
                        f'from atmosphere via surface_input_source=2)')
                    continue

                ds = self.adapter.open_for(group_row, vtable_row)
                if ds is None:
                    continue  # missing file — adapter already warned

                utils.write_log(f'{print_prefix}Loading {varname}')

                # Hybrid-sigma coefficients come from the first 3D Lev var.
                if (lvlmark == 'Lev' and lvltype == '3d'
                        and not hasattr(self, 'ap')):
                    self._extract_hybrid_coeffs(ds)

                # Time slicing decision. fx/monthly/daily fields and BCMM
                # monthly groups carry no extra time cost; standard sub-daily
                # arrays slice to the ETL window to keep memory bounded.
                is_bcmm_monthly = (self.adapter.one_ds_per_group
                                    and str(group_row['var_frq']) == '1M')
                if (lvltype in FIXED_2D_TYPES
                        or lvltype in SOIL_MON_TYPES
                        or lvltype in TIMEDEP_2D_TYPES
                        or is_bcmm_monthly):
                    da = ds[varname]
                else:
                    da = ds[varname].sel(time=slice(
                        self.etl_strt_time.strftime('%Y-%m-%d'),
                        self.etl_end_time.strftime('%Y-%m-%d')))

                # CESM2 6hrLev files can ship variables with inconsistent lev
                # orientation. Canonical ap/b came from the first 3D Lev var;
                # flip any subsequent var whose b differs.
                if (lvlmark == 'Lev' and lvltype == '3d'
                        and 'b' in ds and hasattr(self, 'b')
                        and not np.allclose(ds['b'].values, self.b)):
                    da = da.isel(lev=slice(None, None, -1))
                    utils.write_log(
                        f'{print_prefix}Flipped {varname} along lev '
                        f'(orientation mismatch vs canonical b)')

                # Normalize 3D PlevPt coord name (some models use `lev`).
                if (lvlmark == 'PlevPt' and lvltype == '3d'
                        and 'lev' in da.coords):
                    da = da.rename({'lev': 'plev'})

                # For multi-layer soil sources (e.g. CESM2 tsl with 25
                # native layers), capture depth_bnds so parse_data can do
                # overlap-weighted remapping onto WRF's 4 target layers
                # rather than naively picking by index.
                if lvltype == '2d-soil-mon':
                    depth_dim = next(
                        (d for d in da.dims if d not in ('lat', 'lon', 'time')),
                        None)
                    if depth_dim:
                        bnds = soil_utils.read_depth_bnds(ds, depth_dim)
                        if bnds is not None:
                            self.soil_depth_bnds[varname] = bnds
                            utils.write_log(
                                f'{print_prefix}Captured depth_bnds for '
                                f'{varname} ({bnds.shape[0]} source layers)')

                self.ds[varname] = da

        # CESM2: ps lives in its own file; pick it up from the loaded vars.
        if hasattr(self, 'ap') and 'ps' in self.ds and not hasattr(self, 'ps'):
            self.ps = self.ds['ps']

        self._load_sftlf_helper()
        # All variables have been materialized into self.ds — let the
        # adapter release file handles.
        self.adapter.close()

    def _interp_to_grid(self, da, with_plev=False):
        '''Bilinear interpolation to the configured OutputGrid (lat/lon,
        optionally + plev). One-stop shop so callers stop repeating the
        same xarray.interp kwargs six times.'''
        kw = dict(lat=self.grid.lats, lon=self.grid.lons,
                  method='linear', kwargs={"fill_value": "extrapolate"})
        if with_plev:
            kw['plev'] = self.grid.plev
        return da.interp(**kw)

    def _fill_2d(self, da, src_kind='full'):
        '''Return a copy of `da` with all NaNs (and optionally the off-mask
        side) filled by 2-D nearest-neighbour. `src_kind` selects masking:
          'land': field is defined only over land; sea points -> NaN then fill
          'sea' : field is defined only over sea;  land points -> NaN then fill
          'full': just fill existing NaNs.
        Falls back to the original NaN mask when no sftlf helper is loaded.'''
        arr = np.asarray(da.values, dtype=np.float32).copy()
        if hasattr(self, 'sftlf') and arr.shape == self.sftlf.shape:
            if src_kind == 'land':
                arr = np.where(self.sftlf < 50.0, np.nan, arr)
            elif src_kind == 'sea':
                arr = np.where(self.sftlf >= 50.0, np.nan, arr)
        # else: shape mismatch (e.g. tos on regridded 1° ocean grid vs sftlf
        # on atmosphere grid); the source NaN mask already encodes land/sea
        # so the 2-D nearest fill below is sufficient.
        arr = utils.fill_nan_2d_nearest(arr)
        out = da.copy()
        out.values = arr
        return out

    def parse_data(self, tf):
        '''
        Data parser before write to WRF-Interim:
          1. Interpolating to common mesh
          2. Dealing with missing values
          3. Converting units
        '''
        # Adapter handles the calendar-aware conversion: returns a cftime
        # object for no-leap models, a formatted string otherwise.
        tf_sel = self.adapter.time_to_index(tf)

        for idx, irow in self.meta_rows.iterrows():

            df_vtable=self._load_vtable(irow['variable_group'])

            for idy, itm in df_vtable.iterrows():
                varname=itm['src_v']
                lvltype=str(itm['type'])
                lvlmark=str(itm['lvlmark']) if pd.notna(itm['lvlmark']) else ''
                aim_v=itm['aim_v']

                # Soil rows are skipped for models whose soil_strategy says so
                # — the load step already declined to ingest them, but the
                # vtable iteration still visits these rows. Bail quietly here
                # so no "not loaded" warning spams the log.
                if (lvltype in SOIL_ALL_TYPES
                        and self.adapter.soil_strategy == 'skip'):
                    continue

                # Soil caching gate: WRF only uses soil at t=0; later
                # timestamps just need *some* records to satisfy real.exe's
                # consistency check. We populate self.outfrm at t=0 and
                # reuse the same slab on subsequent calls — `write_wrfinterm`
                # writes that cached slab into every wrfinterm file. Skipping
                # here avoids re-running the depth remap / land-fill / regrid
                # pipeline for each (typically expensive on CESM2's 25-layer
                # source).
                if (lvltype in SOIL_ALL_TYPES
                        and self.soil_init_only
                        and tf != self._soil_first_tf):
                    continue

                # skip variables that were not loaded (file not found)
                if varname not in self.ds:
                    utils.write_log(
                        f'{print_prefix}Skipping {varname} — not loaded', lvl=30)
                    continue

                utils.write_log(
                    print_prefix+'Parsing '+varname+',lvltype='+lvltype+',lvlmark='+lvlmark)

                # time selection: fx and BCMM-monthly carry no time dim;
                # everything else takes nearest-neighbor on the target time.
                is_bcmm_monthly = (self.adapter.one_ds_per_group
                                    and str(irow['var_frq']) == '1M')
                if lvltype in FIXED_2D_TYPES or is_bcmm_monthly:
                    da=self.ds[varname]
                else:
                    da=self.ds[varname].sel(time=tf_sel, method='nearest')

                # unit conversions (idiomatic xarray ops preserve attrs)
                if varname=='mrsos' and itm['units']=='kg/m-3':
                    da = da * 1e-2  # kg m-2 → m3 m-3
                if varname=='tos' and itm['units']=='degC':
                    da = da + 273.15

                if lvltype=='3d':
                    if lvlmark=='Lev':
                        ps_tf=self.ps.sel(time=tf_sel, method='nearest')
                        da=utils.hybrid2pressure(
                            da, self.ap, self.b, ps_tf, plev=self.grid.plev)
                    self.outfrm[varname]=self._interp_to_grid(da, with_plev=True)

                elif lvltype == '2d' or lvltype in TIMEDEP_2D_TYPES:
                    # tos is sea-only; everything else (e.g. ts, ps, tas) is
                    # defined globally.
                    src_kind = 'sea' if varname == 'tos' else 'full'
                    da = self._fill_2d(da, src_kind=src_kind)
                    self.outfrm[varname]=self._interp_to_grid(da)

                elif lvltype in FIXED_2D_TYPES:
                    self.outfrm[varname]=self._interp_to_grid(da)

                elif lvltype == '2d-soil-mon':
                    # Remap from the source's native depth axis onto the WRF
                    # target layer parsed out of aim_v (e.g. 'ST040100' →
                    # 40-100 cm). When depth_bnds are available (captured at
                    # load time for this varname), overlap-weighted averaging
                    # is used; otherwise fall back to nearest-center.
                    depth_dim = next(
                        (d for d in da.dims if d not in ('lat', 'lon', 'time')),
                        None)
                    if depth_dim is None:
                        # Source has no depth axis (single-layer); just take it.
                        da_lyr = da
                    else:
                        lo_cm, hi_cm = soil_utils.parse_wrf_soil_label(aim_v)
                        da_lyr = soil_utils.remap_soil_layer(
                            da, depth_dim, lo_cm, hi_cm,
                            depth_bnds=self.soil_depth_bnds.get(varname))
                    da_lyr = self._fill_2d(da_lyr, src_kind='land')
                    self.outfrm[aim_v]=self._interp_to_grid(da_lyr)

                elif lvltype == '2d-soilr-mon':
                    # single-layer variable repeated for all soil levels
                    da = self._fill_2d(da, src_kind='land')
                    self.outfrm[aim_v]=self._interp_to_grid(da)

                elif lvltype in ('2d-soil', '2d-soilr'):
                    # 2d-soilr is the "repeat" variant — when a model only
                    # publishes 0-10cm soil but we still need the 10-200cm
                    # slot filled (e.g. MPI-ESM1-2-HR historical), the vtable
                    # lists the same src_v under a 2d-soilr row with a
                    # different aim_v label. We do the same interp; the
                    # write side picks the right label.
                    da = self._fill_2d(da, src_kind='land')
                    self.outfrm[varname]=self._interp_to_grid(da)

    def write_wrfinterm(self, tf, tgt):
        if tgt=='main':
            out_fn=self.out_root+'/'+self.model_name+':'+tf.strftime('%Y-%m-%d_%H')
        if tgt=='sst':
            out_fn=self.out_root+'/'+self.model_name+'_SST:'+tf.strftime('%Y-%m-%d_%H')

        utils.write_log(print_prefix+'Writing '+out_fn)
        wrf_mid = FortranFile(out_fn, 'w', header_dtype=np.dtype('>u4'))

        out_dic=self.out_slab
        out_dic['HDATE']=tf.strftime('%Y-%m-%d_%H:%M:%S:0000')

        for idx, irow in self.meta_rows.iterrows():

            df_vtable=self._load_vtable(irow['variable_group'])

            for idy, itm in df_vtable.iterrows():
                if (tgt == 'sst' and itm['aim_v'] != 'SST'):
                    continue
                if (tgt == 'main' and itm['aim_v'] == 'SST'):
                    continue
                varname=itm['src_v']
                lvltype=itm['type']
                aim_v=itm['aim_v']

                # NOTE: when soil_init_only=true, soil records are still
                # *written* at every time — but `self.outfrm[...]` was only
                # populated at t=0 (see the matching gate in parse_data), so
                # every wrfinterm gets the same cached t=0 slab. real.exe's
                # structural-consistency check is happy; the LSM never reads
                # t>0 soil anyway, so physics are unchanged.

                # Adapter-level soil opt-out: don't emit soil records when
                # the model's soil data isn't trustworthy.
                if (lvltype in SOIL_ALL_TYPES
                        and self.adapter.soil_strategy == 'skip'):
                    continue

                # skip variables that were not loaded (file not found)
                lookup_key = aim_v if lvltype in ['2d-soil-mon', '2d-soilr-mon'] else varname
                if lookup_key not in self.outfrm:
                    utils.write_log(
                        f'{print_prefix}Skipping {aim_v} — not in outfrm', lvl=30)
                    continue

                out_dic['FIELD']=aim_v
                out_dic['UNIT']=itm['units'].strip()
                out_dic['DESC']=itm['desc'].strip()
                out_dic['XLVL']=utils.XLVL_SURFACE

                if varname=='tos':
                    out_dic['UNIT']='K'

                if lvltype=='3d':
                    for lvl in self.grid.plev:
                        out_dic['XLVL']=lvl
                        out_dic['SLAB']=self.outfrm[varname].sel(plev=lvl).values
                        utils.write_record(wrf_mid, out_dic)

                elif lvltype == '2d' or lvltype in TIMEDEP_2D_TYPES:
                    if varname in ['ta', 'ua', 'va', 'hur', 'hus']:
                        out_dic['SLAB']=self.outfrm[varname].sel(plev=100000.0).values
                    else:
                        out_dic['SLAB']=self.outfrm[varname].values
                    utils.write_record(wrf_mid, out_dic)

                elif lvltype in FIXED_2D_TYPES:
                    out_dic['SLAB']=self.outfrm[varname].values
                    utils.write_record(wrf_mid, out_dic)

                elif lvltype in ['2d-soil-mon', '2d-soilr-mon']:
                    out_dic['SLAB']=self.outfrm[aim_v].values
                    utils.write_record(wrf_mid, out_dic)

                elif lvltype in ('2d-soil', '2d-soilr'):
                    index = next(
                        (i for i, s in enumerate(self.grid.soil_layers) if s in aim_v), None)
                    if self.adapter.soil_packed_4d:
                        out_dic['SLAB']=self.outfrm[varname].values[:,index,:,:]
                    else:
                        # 2d-soilr: same slab as the 2d-soil row processed
                        # earlier in this iter for the same src_v, written
                        # under a different aim_v (e.g. ST010200 vs ST000010).
                        out_dic['SLAB']=self.outfrm[varname].values
                    utils.write_record(wrf_mid, out_dic)

        wrf_mid.close()


if __name__ == "__main__":
    pass
