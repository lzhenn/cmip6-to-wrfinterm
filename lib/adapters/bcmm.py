"""BCMM (Bias-corrected CMIP6 Multi-Model) layout.

Unlike standard CMIP6, BCMM packs every variable in a `variable_group`
into one monthly NetCDF file. Filenames follow the `naming_convention`
column of `cmip6_meta.csv` (e.g. `atm_SCENARIO_YYYY_MM.nc4`), with
placeholders substituted from the ETL start time + scenario.

Because one file carries many variables, the adapter sets
`one_ds_per_group = True` so the file is opened once per group and
re-used for every vtable row.
"""
from lib.adapters._base import ModelAdapter


class BcmmAdapter(ModelAdapter):
    one_ds_per_group = True
    soil_packed_4d = True

    def _files_for(self, group_row, vtable_row):
        fn = group_row['naming_convention']
        fn = fn.replace('SCENARIO', self.scenario)
        fn = fn.replace('YYYY', self.etl_strt_time.strftime('%Y'))
        fn = fn.replace('MM', self.etl_strt_time.strftime('%m'))
        return f"{self.in_root}/{fn}"
