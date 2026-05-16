"""Model adapters: encapsulate per-model data layout differences (file
discovery, dataset opening, calendar/time handling) so the core handler
stays model-agnostic.

Adding a new CMIP6 model usually means *no code change* — just point the
config at it. Non-standard layouts (e.g. BCMM's many-vars-per-file) get a
dedicated subclass.
"""
from lib.adapters._base import ModelAdapter
from lib.adapters.cmip6 import Cmip6Adapter
from lib.adapters.bcmm import BcmmAdapter


# Models that use non-standard calendars (no-leap, 360-day, ...) and need
# xarray's cftime backend. New models can either be added here or signal
# via a `calendar = noleap` line in their [INPUT] section.
CFTIME_MODELS = {'CESM2'}

# Models whose published soil profile is surface-only — any "deep" layers
# we manufacture are fabrications. Two valid mitigations exist, and the
# choice between them is a research-design call rather than something
# c2w should make on the user's behalf:
#
#   1. Keep the (cosmetically dishonest) legacy behaviour: write four
#      copies of the surface layer under the four WRF aim_v labels.
#      Noah LSM is happy, but deep-layer values are not real. README
#      warns; users supply long spin-up (>=1 month).
#
#   2. Opt into soil_strategy='skip' on the adapter: c2w drops soil
#      records, emits a hints sidecar pointing the WRF namelist at
#      `num_metgrid_soil_levels=0 + surface_input_source=2`. This is
#      WRF-recommended for missing soil, **but** Noah LSM
#      (sf_surface_physics=2) still wants soil T at init; this combo
#      therefore requires `sf_surface_physics=1` (5-layer thermal
#      diffusion) in your namelist.input.
#
# Default below = empty: every model gets 'native', which preserves the
# pre-existing legacy behaviour. Flip a model into the set (or set
# adapter.soil_strategy='skip' manually) to opt into option 2.
SOIL_FALLBACK_MODELS = set()


def make_adapter(in_cfg, scenario, etl_strt_time, etl_end_time):
    '''Factory: pick the right adapter for this config.

    - `BCMM` → BcmmAdapter (one file holds many variables, monthly chunks)
    - everything else → Cmip6Adapter (one file per variable, glob OR exact
      discovery depending on whether `cmip_strt_ts` is present)

    The factory keeps CMIPHandler free of model-name branches.
    '''
    name = in_cfg['model_name']
    if name == 'BCMM':
        adapter = BcmmAdapter(name, in_cfg, scenario, etl_strt_time, etl_end_time)
    else:
        calendar = in_cfg.get('calendar', 'standard') if hasattr(in_cfg, 'get') else 'standard'
        use_cftime = (name in CFTIME_MODELS) or (calendar.lower() != 'standard')
        adapter = Cmip6Adapter(
            name, in_cfg, scenario, etl_strt_time, etl_end_time,
            use_cftime=use_cftime)

    if name in SOIL_FALLBACK_MODELS:
        adapter.soil_strategy = 'skip'
    return adapter


__all__ = ['ModelAdapter', 'Cmip6Adapter', 'BcmmAdapter',
           'make_adapter', 'CFTIME_MODELS', 'SOIL_FALLBACK_MODELS']
