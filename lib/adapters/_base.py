"""ModelAdapter base class.

A ModelAdapter owns three responsibilities:
  1. Locate input file(s) for a given (variable_group, source_variable) pair.
  2. Open them as an xarray.Dataset (with the right calendar backend).
  3. Translate a python datetime into whatever coord type the dataset's
     time axis uses (string for cftime=False, cftime.Datetime* otherwise).

It also caches opened datasets so a model that packs many variables into
one file (BCMM) only opens that file once.
"""
from abc import ABC, abstractmethod

import xarray as xr

from utils import utils


class ModelAdapter(ABC):
    """Abstract base. Subclasses implement `_files_for`."""

    #: Whether xarray.open_* needs `use_cftime=True` (no-leap & friends).
    use_cftime = False

    #: If True, one file holds every variable in a `variable_group` (BCMM).
    #: If False, every (group, src_v) pair maps to its own file (CMIP6 norm).
    one_ds_per_group = False

    #: If True, multi-layer soil vars (`2d-soil`) are stored as a single 4-D
    #: array (time, layer, lat, lon) and need slicing by layer index at
    #: write time (BCMM). The CMIP6 norm is one DataArray per layer name.
    soil_packed_4d = False

    #: How to handle multi-layer soil records when feeding WRF.
    #:   'native' (default)
    #:       Write soil records from CMIP data. Multi-layer sources are
    #:       remapped onto WRF's four standard layers by overlap-weighted
    #:       averaging (utils.soil.remap_soil_layer). CESM2, BCMM use this.
    #:   'skip'
    #:       Do *not* write any soil records — c2w produces no soil-typed
    #:       output. The handler emits a `<MODEL>.namelist_hints.json`
    #:       sidecar telling downstream WRF to use
    #:           num_metgrid_soil_levels = 0
    #:           surface_input_source   = 2
    #:       so real.exe interpolates soil temperature from the atmospheric
    #:       column instead of ingesting fabricated layers. This is the
    #:       honest choice for models that only publish surface-only soil
    #:       (MPI-ESM1-2-HR, EC-Earth3 historical).
    soil_strategy = 'native'

    def __init__(self, model_name, in_cfg, scenario,
                 etl_strt_time, etl_end_time):
        self.model_name = model_name
        self.in_cfg = in_cfg
        self.in_root = in_cfg['input_root'].rstrip('/')
        self.scenario = scenario
        self.etl_strt_time = etl_strt_time
        self.etl_end_time = etl_end_time
        # cache: cache_key -> Dataset (or None for "tried and missing")
        self._cache = {}

    # ---- subclass contract ------------------------------------------------

    @abstractmethod
    def _files_for(self, group_row, vtable_row):
        '''Return path(s) for the variable, or None if missing on disk.

        Return types:
          - str         : a single .nc file
          - List[str]   : multiple chunks (open_mfdataset)
          - None        : file not found — caller will skip the variable
        '''

    # ---- public API used by CMIPHandler -----------------------------------

    def open_for(self, group_row, vtable_row):
        '''Return the Dataset containing `vtable_row['src_v']`, or None.

        Caching is keyed by group_name when `one_ds_per_group` (BCMM), else
        by (group_name, src_v).
        '''
        key = self._cache_key(group_row, vtable_row)
        if key in self._cache:
            return self._cache[key]
        files = self._files_for(group_row, vtable_row)
        if files is None:
            self._cache[key] = None
            return None
        ds = self._open(files)
        self._cache[key] = ds
        return ds

    def time_to_index(self, tf):
        '''Convert a python datetime into something usable by .sel(time=...).
        cftime-calendared datasets need a cftime object; others take a
        formatted string.'''
        if self.use_cftime:
            import cftime
            return cftime.DatetimeNoLeap(
                tf.year, tf.month, tf.day, tf.hour, tf.minute, tf.second)
        return tf.strftime('%Y-%m-%d %H:%M:%S')

    def close(self):
        '''Release cached file handles.'''
        for ds in self._cache.values():
            if ds is None:
                continue
            try:
                ds.close()
            except Exception:
                pass
        self._cache.clear()

    # ---- helpers ----------------------------------------------------------

    def _cache_key(self, group_row, vtable_row):
        if self.one_ds_per_group:
            return group_row['variable_group']
        return (group_row['variable_group'], vtable_row['src_v'])

    def _open(self, files):
        '''Default opener; subclasses rarely need to override.'''
        kw = {'use_cftime': True} if self.use_cftime else {}
        if isinstance(files, list):
            if len(files) == 1:
                return xr.open_dataset(files[0], **kw)
            return xr.open_mfdataset(files, combine='by_coords', **kw)
        return xr.open_dataset(files, **kw)
