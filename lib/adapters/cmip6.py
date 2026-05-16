"""Standard CMIP6 layout: one file per variable, DRS filename.

Filename pattern (CMIP6 DRS):
    <var>_<table>_<source>_<experiment>_<member>_<grid>[_<time-range>].nc

Two discovery strategies are supported, auto-selected:

* **exact**  — config provides `cmip_strt_ts` / `cmip_end_ts`, used to build
  the trailing `_YYYYMMDDHHMM-YYYYMMDDHHMM.nc` suffix verbatim. This is the
  legacy MPI-ESM1-2-HR / EC-Earth3 path.

* **glob**   — config does *not* provide those keys. We `glob` for any
  matching `<stem>_*.nc` (or `<stem>.nc` for fx/time-invariant). This is
  much more tolerant to the unpredictable chunk-time-suffix in real CMIP6
  data and is the CESM2 path.
"""
import glob

import pandas as pd

from lib.adapters._base import ModelAdapter
from utils import utils


print_prefix = 'lib.adapters.cmip6>>'


class Cmip6Adapter(ModelAdapter):
    one_ds_per_group = False

    def __init__(self, model_name, in_cfg, scenario,
                 etl_strt_time, etl_end_time, use_cftime=False):
        super().__init__(model_name, in_cfg, scenario,
                         etl_strt_time, etl_end_time)
        self.use_cftime = use_cftime
        self.esm_flag = in_cfg['esm_flag']
        self.grid_flag = in_cfg['grid_flag']
        # Auto-pick discovery strategy from config presence.
        self.discovery = 'exact' if 'cmip_strt_ts' in in_cfg else 'glob'
        if self.discovery == 'exact':
            self.cmip_strt_ts = in_cfg['cmip_strt_ts']
            self.cmip_end_ts = in_cfg['cmip_end_ts']

    # ------------------------------------------------------------------

    def _files_for(self, group_row, vtable_row):
        varname = vtable_row['src_v']
        lvlmark = vtable_row.get('lvlmark', '')
        if pd.isna(lvlmark) or str(lvlmark) == 'None':
            lvlmark = ''
        else:
            lvlmark = str(lvlmark)

        file_scenario = self._file_scenario()
        table_name = self._table_name(group_row, lvlmark)

        stem = (f"{self.in_root}/{varname}_{table_name}_{self.model_name}"
                f"_{file_scenario}_{self.esm_flag}_{self.grid_flag}")

        if self.discovery == 'glob':
            matches = (sorted(glob.glob(stem + '_*.nc'))
                       + sorted(glob.glob(stem + '.nc')))
            if not matches:
                utils.write_log(
                    f'{print_prefix}WARNING: no file for {varname} '
                    f'(stem: {stem})', lvl=30)
                return None
            return matches

        # exact discovery: classic MPI/EC-Earth3 path
        return f"{stem}_{self.cmip_strt_ts}-{self.cmip_end_ts}.nc"

    # ------------------------------------------------------------------

    def _file_scenario(self):
        '''Map config scenario string to the literal that appears in DRS
        filenames. CESM2 configs say `hist`, files say `historical`; SSPs
        match verbatim.'''
        if self.scenario == 'hist':
            return 'historical'
        return self.scenario

    def _table_name(self, group_row, lvlmark):
        '''Resolve the CMIP6 table id (Amon, 6hrLev, 3hr, fx, ...).

        Prefers an explicit `table_id` column on the meta row. Falls back
        to `<frq>r<lvlmark>` (the MPI-style implicit convention) if absent.
        '''
        tid = group_row.get('table_id', '') if hasattr(group_row, 'get') else ''
        if pd.isna(tid):
            tid = ''
        tid = str(tid).strip()
        if tid and tid.lower() != 'nan':
            return tid
        frq = str(group_row['var_frq']).replace('*', '')
        return frq + 'r' + lvlmark
