# cmip6-to-wrfinterm
- [cmip6-to-wrfinterm](#cmip6-to-wrfinterm)
  - [Supported GCMs](#supported-gcms)
  - [Installation](#installation)
  - [Quick start](#quick-start)
    - [MPI-ESM-1-2-HR (Default)](#mpi-esm-1-2-hr-default)
    - [BCMM](#bcmm)
    - [EC-Earth3](#ec-earth3)
    - [CESM2](#cesm2)
  - [Output file naming](#output-file-naming)
  - [Usage](#usage)
    - [Modify config.ini (`MPI-ESM1-2-HR`)](#modify-configini-mpi-esm1-2-hr)
    - [\[OPTIONAL\] Modify Vtable](#optional-modify-vtable)
    - [\[Advanced\] cmip\_handler.py](#advanced-cmip_handlerpy)
  - [Troubleshooting](#troubleshooting)
    - [\[Appendix\] Fetch Input Files](#appendix-fetch-input-files)

**I was mass-producing excuses to abandon this repo ("gotta make money!"), but [Claude](https://claude.ai/) dragged me back to fill the holes I left behind. Issues and PRs are welcome again!**

**CMIP6-to-WRFInterim** uses pure python implementation to convert CMIP6 sub-daily output into WRF intermediate files, which are used to drive the WRF model for regional dynamical downscaling usage.
Current supported models are listed below. If you hope to use other models, proper modifications are needed.

## Supported GCMs

| Model Name                    | historical    | SSP126   | SSP245   | SSP585   |
| ----                          | ----          | ----     | ----     | ----     | 
|Bias-corrected Multi-Model [^1]|               | N/A      | &#10004; | &#10004; | 
|MPI-ESM-1-2-HR                 | &#10004;      | &#10004; | &#10004; | &#10004; | 
|EC-Earth3                      | &#10004;[^2]  |          |          |          | 
|CESM2                          | &#10004;      |          |          |          |

[^1]: https://www.scidb.cn/en/detail?dataSetId=791587189614968832 
[^2]: Only done limited tests.

<img src="https://raw.githubusercontent.com/Novarizark/cmip6-to-wrfinterm/master/fig/sample_skintemp.png" alt="drawing" style="width:400px;"/><img src="https://raw.githubusercontent.com/Novarizark/cmip6-to-wrfinterm/master/fig/skintemp006hr.png" alt="drawing" style="width:400px;"/>

## Installation
Please install python3 using Anaconda3 distribution. [Anaconda3](https://www.anaconda.com/products/individual) with python3.8 and 3.9 has been deeply tested, lower version of python3 may also work (without testing). If `numpy`, `pandas`, `scipy`, `xarray`, `netcdf4` are properly installed, you may skip the installation step.

While, we recommend to create a new environment in Anaconda:

```bash
conda env create -f test_c2w.yml
conda activate test_c2w
```

If you prefer `pip`, a minimal `requirements.txt` is also provided:

```bash
pip install -r requirements.txt
```

## Quick start

### MPI-ESM-1-2-HR (Default)
```bash
# fetch the sample period first (sample/*/*.nc is not in git):
bash sample/MPI-ESM1-2-HR/download.sh
# convert:
python3 run_c2w.py
```

Please use a Unix-like (Linux) system to run the above commands, and it is okay to see some FutureWarnings. If successful, you should see `MPI-ESM1-2-HR:2100-01-02_00` and `MPI-ESM1-2-HR:2100-01-02_06` in the `./output` folder (see [Output file naming](#output-file-naming)).
(See [Troubleshooting](https://github.com/lzhenn/cmip6-to-wrfinterm#troubleshooting) if you are a Windows Subsystem user.)

Copy or link the two intermediate files to your WPS folder, prepare your **geo_em** files and setup your `namelist.wps` properly, now you are ready to run `metgrid.exe` and the following WRF procedures. There is a simple `namelist.wps` and `namelist.input` covering the East Asian region in `./sample/MPI-ESM-1-2-HR/`. You can also modify `wps_wrf_pipeline.sh` to automate the chain from `metgrid.exe` to `wrf.exe` on a computing node.

If you run the sample case successfully, you are expected to see snapshots of the skin temperature in the initial condition and after 6-hour WRFv4.3 run as shown above.

### BCMM
```bash
python3 run_c2w.py -m BCMM
```
This will use [the Bias-corrected CMIP6 Multi-model dataset](https://www.scidb.cn/en/detail?dataSetId=791587189614968832).

> **Note**: `./sample/BCMM/` only contains `download.sh` (and a sample `namelist.*`). You need to fetch the data yourself before running — see `bash sample/BCMM/download.sh` or download manually from the source listed above.

### EC-Earth3
```bash
python3 run_c2w.py -m EC-Earth3
```
Single command — produces all atmospheric + surface intermediate files in one pass. EC-Earth3 is now split across three meta rows (`LEV` for 6-hourly hybrid 3-D, `PLEV6H` for 6-hourly geopotential/MSLP, `SURF3H` for 3-hourly near-surface + soil) so the handler discovers each variable from its native CMIP6 table.

> **Note**: `./sample/EC-Earth3/` ships only `namelist.{wps,input}` (no NetCDF). Fetch the data from [ESGF](https://esgf-node.llnl.gov/search/cmip6/) (search `source_id=EC-Earth3, experiment_id=historical, variant_label=r1i1p1f1`) into `sample/EC-Earth3/`. SST (`tos`) is on the `gn` (native ocean) grid and currently skipped — atmospheric c2w runs are unaffected; if you need SST, see the open issue list.

If you run the sample case successfully, you are expected to see snapshots of the skin temperature in the initial condition and after 6-hour WRFv4.3 run as shown as below. Thanks [Dr. Tito Maldonado from University of Costa Rica](https://cigefi.ucr.ac.cr/team/tito-maldonado-phd/) for helping with the EC-Earth3 support.

<img src="https://github.com/lzhenn/cmip6-to-wrfinterm/blob/master/fig/EC_EARTH3_skintemp_sample_00.png" alt="drawing" style="width:400px;"/>
<img src="https://github.com/lzhenn/cmip6-to-wrfinterm/blob/master/fig/EC_EARTH3_skintemp_sample_06.png" alt="drawing" style="width:400px;"/>

### CESM2
```bash
python3 run_c2w.py -m CESM2
```
This drives [CESM2](https://www.cesm.ucar.edu/models/cesm2) (CMIP6, ensemble `r11i1p1f1`, historical experiment). The Vtables, meta, and config are bundled (`db/CESM2_*.csv`, `conf/config.CESM2.ini`), and CESM2 follows the **single-run** workflow — one invocation produces all main + SST intermediate files, no need for the multi-pass EC-Earth3 dance.

> **Note**: `./sample/CESM2/` only ships a `download.sh` helper, no NetCDF files. Before running you must fetch the data — see [Appendix: Fetch Input Files](#appendix-fetch-input-files). Known caveat: on hosts with old `glibc` / restricted HTTPS the bundled ESGF download script may fail; in that case download manually from [esgf-node.llnl.gov](https://esgf-node.llnl.gov/search/cmip6/) (search `source_id=CESM2`, `experiment_id=historical`, `variant_label=r11i1p1f1`) or use a mirror / Globus.

CESM2 specifics handled internally:
- no-leap (365-day) calendar via `use_cftime=True`
- monthly soil (`tsl`, `mrsos`) interpolated to the requested 6-hourly target time
- daily SST (`tos`) interpolated to the target time

A 24-hour WRF run driven by CESM2 boundary conditions is shown in `fig/cesm2_wrf_24h.gif`.

## Output file naming

Every model produces files in `[OUTPUT]['output_root']` with this convention:

```
<model_name>:YYYY-MM-DD_HH        # main atmospheric / land record
<model_name>_SST:YYYY-MM-DD_HH    # SST record (BCMM and CESM2 only)
```

`<model_name>` is read verbatim from `[INPUT]['model_name']` in the config (e.g. `MPI-ESM1-2-HR`, `BCMM`, `EC-Earth3`, `CESM2`). When wiring up `metgrid.exe`, point the `&metgrid` `fg_name` list at these prefixes. The `output_prefix` key that appears in some configs is **not** consumed by the current code — only `model_name` matters.

## Usage

### Modify config.ini (`MPI-ESM1-2-HR`)

When you properly download the `MPI-ESM1-2-HR` data, First edit the `./conf/config.MPI-ESM1-2-HR.ini` file properly.

``` python
[INPUT]
input_root=./sample/MPI-ESM1-2-HR/
model_name=MPI-ESM1-2-HR
scenario = ssp585
esm_flag=r1i1p1f1
grid_flag=gn
#YYYYMMDDHHMM
cmip_strt_ts = 210001020000
cmip_end_ts = 210001020600

[OUTPUT]
#YYYYMMDDHHMM, please seperate your ETL processes if request very long-term simulation
etl_strt_ts = 210001020000
etl_end_ts = 210001020600
output_root = ./output/
``` 

* `[INPUT]['input_root']` is the root directory of the CMIP6 data, here it points to the `./sample/` folder.
* `[INPUT]['model_name']` is the name of the model. Now only the `MPI-ESM-1-2-HR` model is supported. If you plan to use other models, you need to setup your own variable mapping table (see below).

* `[INPUT]['scenario']` `['esm_flag']` `['grid_flag']` are used to form the netCDF file names.
* `[INPUT]['cmip_strt_ts']` and `[INPUT]['cmip_end_ts']` are the start and end time of the CMIP6 data.
* `[OUTPUT]['etl_strt_ts']` and `[OUTPUT]['etl_end_ts']` are the start and end time of your desired ETL period.

After you have edited the `config.ini` file, you can run the script again for your desired period. The intemediate files will be generated in the `[OUTPUT]['output_root']` folder. 

**Soil-data handling.** Each model adapter declares a `soil_strategy` (in `lib/adapters/__init__.py`):

* **`native`** (default for all models) — soil records are written from the source CMIP data:
  * **Multi-layer source with `depth_bnds`** (e.g. CESM2 with 25 native layers spanning 1 cm to 42 m) — handler does an **overlap-weighted vertical remap** (`utils/soil.py`) onto WRF's standard `ST/SM 000010 / 010040 / 040100 / 100200`. Without `depth_bnds`, falls back to nearest-center on the depth axis.
  * **Single-layer / surface-only source** (e.g. MPI-ESM1-2-HR's `mrsos`/`tsl`, EC-Earth3's `tslsi`) — vtable rows with type `2d-soilr` (the "repeat" variant) duplicate the surface layer into the deep WRF slots. **These deep values are NOT real physics**; they exist so `real.exe`'s Noah LSM gets the four soil records it requires at init. A long spin-up (≥1 month) is essential when accurate soil state matters.
* **`skip`** (opt-in only — *not* the default for any model in the repo today) — c2w omits soil records entirely and drops a `<MODEL>.namelist_hints.json` sidecar telling the run script to set
  ```
  num_metgrid_soil_levels = 0
  surface_input_source    = 2
  ```
  in `namelist.input`. This is the WRF-recommended fallback for missing soil data, **but** the Noah LSM (`sf_surface_physics=2`) still requires init soil T, so this combo additionally needs `sf_surface_physics=1` (5-layer thermal diffusion). Picking this is a research-design call, not something the tool decides for you.

**Soil init-only caching** (`[OUTPUT] soil_init_only`, default `true`). WRF's LSM only consumes soil at t=0; later met_em files are read by `real.exe` for the structural-consistency check but their soil values are never used by the LSM math. We exploit this: the depth-remap / land-fill / regrid pipeline runs once at t=0, caches the result in `self.outfrm`, and every subsequent wrfinterm writes the same cached slab. real.exe sees soil records at every time (happy), and the physics are identical to running it per-time. Saves substantial CPU on long batches — particularly for CESM2 (25-layer overlap-weighted remap × N timestamps → × 1). Set to `false` only if you're doing something downstream that actually inspects t>0 metgrid soil (e.g. a custom soil-nudging chain).

For historical run, `MPI-ESM1-2-HR` do not provide skin temp output in atmospheric dataset, we use `tas` here to represent the skin temp, which is acceptable over land as the land properties are prognostic from the land surface model, but it may have bias for the prescribed `SST`. 
We suggest the user download `tos` data from the ocean data set and convet it to atmosphreic data set format, and modify the `Vtable` to ingest the true SST.

### [OPTIONAL] Modify Vtable 

`./db/${MODEL_NAME}.csv` records the model-specified variable mapping table. If you plan to use other models or involve SST in certain cases (e.g. historical run of MPI-ESM1-2-HR), you need to setup your own variable mapping table. 

``` javascript 
src_v,aim_v,units,type,lvlmark,desc
ta,TT,K,3d,PlevPt,3-d air temperature
hus,SPECHUMD,kg kg-1,3d,PlevPt,3-d specific humidity
ua,UU,m s-1,3d,PlevPt, 3-d wind u-component
va,VV,m s-1,3d,PlevPt, 3-d wind v-component
zg,GHT,m,3d,PlevPt, 3-d geopotential height
ps,PSFC,Pa,2d,Lev, Surface pressure
tas,TT,K,2d,PlevPt, 2-m temperature
uas,UU,m s-1,2d,PlevPt, 10m wind u-component
vas,VV,m s-1,2d,PlevPt, 10m wind v-component
ts,SKINTEMP,K,2d,PlevPt, Skin temperature
psl,PMSL,Pa,2d,PlevPt, Mean sea-level pressure
huss,SPECHUMD, kg kg-1,2d,PlevPt, 2-m relative humidity
mrsos,SM000010, kg/m-3,2d-soil,PlevPt, 0-10 cm soil moisture
tsl,ST000010,K,2d-soil,PlevPt, 0-10 cm soil temp 
mrsos,SM010200, kg/m-3,2d-soilr,PlevPt, 10-200 cm soil moisture
tsl,ST010200,K,2d-soilr,PlevPt, 10-200 cm soil temp 
```

* `src_v` is the name of the variable in the CMIP6 data, which is also used to form the netCDF file name.
* `aim_v` is the name of the variable archived in WRF intermidiate file, which is used by `metgrid.exe`.
* `units` is the unit of the variable.
* `type` denotes the variable kind. Recognised values:
  * `3d` — 3-D atmospheric field. `lvlmark=Lev` for hybrid-sigma source (handler converts to pressure via `hybrid2pressure`); `lvlmark=PlevPt` for already-on-pressure source.
  * `2d` — 2-D surface field at a fixed level (`ps`, `tas`, `huss`, `ts`, ...).
  * `2d-fixed` — time-invariant 2-D (`orog`, `sftlf`).
  * `2d-mon` / `2d-daily` — 2-D field on monthly/daily cadence, snapped to the target time (`ts`, `tos`).
  * `2d-soil-mon` — multi-layer monthly soil on a native depth axis. The handler does overlap-weighted depth remapping onto the WRF target layer encoded in `aim_v` (e.g. `ST040100` → 40-100 cm). Requires `depth_bnds` in the source NetCDF.
  * `2d-soilr-mon` — single-layer monthly soil, replicated across all 4 WRF layers (e.g. CESM2 `mrsos` is published as a single 0-10 cm value).
  * `2d-soil` / `2d-soilr` — legacy types kept for BCMM (which packs 4 layers into one DataArray). For models that lack a usable deep-soil profile (MPI-ESM1-2-HR, EC-Earth3), these rows are ignored at runtime when the adapter's `soil_strategy='skip'`.
* `lvlmark` is the level mark of the variable. `PlevPt` means the variable is a 3-d variable with pressure level.
* `desc` is the description of the variable.

### [Advanced] Architecture

```
run_c2w.py                       — CLI entry; iterates time series, calls handler
└── lib/cmip_handler.CMIPHandler — orchestrates load → parse → write
    ├── lib/adapters/            — model-specific file discovery + dataset opening
    │   ├── _base.ModelAdapter         abstract: open_for, time_to_index, close
    │   ├── cmip6.Cmip6Adapter         standard CMIP6 (MPI / EC-Earth3 / CESM2)
    │   │   ├── discovery = "glob"     no cmip_strt_ts → tolerates unknown time suffix
    │   │   ├── discovery = "exact"    has cmip_strt_ts → builds filename verbatim
    │   │   └── use_cftime             auto-on for CFTIME_MODELS (CESM2) or [INPUT] calendar=noleap
    │   └── bcmm.BcmmAdapter           BCMM packs many vars into one monthly nc4 file
    ├── utils/grid.OutputGrid    — lat/lon mesh, plev levels, soil layers (override via [OUTPUT])
    └── utils/soil               — overlap-weighted depth remap (CESM2's 25-layer → WRF's 4)
```

### Adding a new model

In ≈ four small files (no Python edits needed for most CMIP6 sources):

1. **`db/<MODEL>_<group>.csv` (one or more)** — variable map. Each row is one (source variable, WRF aim_v, type) entry. See `db/CESM2_6hrLev.csv` as the cleanest template.
2. **`db/cmip6_meta.csv`** — add one row per CMIP6 table you'll consume, with `variable_group` matching the vtable filename and an explicit `table_id` (e.g. `6hrLev`, `Lmon`, `fx`). Mark exactly one row with `var_frq=Nh*` (the master cadence — drives `out_time_series`).
3. **`conf/config.<MODEL>.ini`** — minimum keys: `[INPUT] input_root, model_name, scenario, esm_flag, grid_flag`; `[OUTPUT] etl_strt_ts, etl_end_ts, output_root`. Omit `cmip_strt_ts/end_ts` to use glob discovery (recommended). Add `calendar = noleap` if your model uses a non-standard calendar.
4. **`sample/<MODEL>/`** — drop a `download.sh` plus `namelist.{wps,input}` so end-to-end testing is reproducible. Don't commit NetCDF; they're gitignored.

Only models with non-standard layouts (multi-var-per-file, weird directory hierarchies) require a new `lib/adapters/<model>.py` — copy `bcmm.py` as a starting point.

## Troubleshooting

**(Dec 19, 2022)**: Lack of suitable source variables from CMIP6 datasets to drive the dynamical downscaling are common. For example, the available 6-hour `ts` variable in SSP is missing in historical run of `MPI-ESM1-2-HR` output. We cannot directly map the `SST` by `ts`.
One trade-off is using the `tas` to represent both the land surface and sea surface temperature, just as you could find in the `MPI-ESM1-2-HR_HIST.csv` vtable. While this is not a good strategy. 
For accurate representation of sea surface temperature, you may need to use 3-hour `tos` variable to generate the SST in historical run (see the Vtable with suffix `SST`). (Thanks [Dr. Paul Nalon from ICHEC](https://www.ichec.ie/staff/paul-nolan-phd) and [Dr. Sium Gebremariam from PSU](http://www.met.psu.edu/people/stg5265) helping with this.) 

**(Nov 27, 2022)**: According to feedback from several users, if you are using Windows Subsystem for Linux (WSL, typically Ubuntu from Microsoft Store), please note Windows does **NOT** support colon ":" in the file name.
You may rename the output file name or try a pure Linux platform.


### [Appendix] Fetch Input Files

CMIP6 source data is **not bundled with the repo** (it's hundreds of MB of binary NetCDF — keeping it in git makes the repo unwieldy to clone). Each model's `sample/<MODEL>/` directory ships with a `download.sh` helper plus example WRF namelists; run the download script once to pull data into the same directory, then run `python3 run_c2w.py -m <MODEL>` as usual.

For **CESM2** you can also produce a tiny synthetic test batch (10×20 grid, 5 timesteps, ~300 KB) instead of downloading real data:
```bash
python3 sample/CESM2/gen_fake_data.py
```
Useful for CI / smoke tests that don't need the real 36 MB-per-file CMIP6 chunks.

According to WRF Users Guide (v4.2), P3-36:
> **Required Meteorological Fields for Running WRF**
>> In order to successfully initialize a WRF simulation, the real.exe pre-processor requires a 
>> minimum set of meteorological and land-surface fields to be present in the output from 
>> the metgrid.exe program. Accordingly, these required fields must be available in the 
>> intermediate files processed by metgrid.exe. 

CMIP6 data can be downloaded from the [LLNL interface](https://esgf-node.llnl.gov/search/cmip6/), after cross-check the variable list from **MPI-ESM-1-2-HR** and the WRF required variables, we have the following table:
![](https://raw.githubusercontent.com/Novarizark/cmip6-to-wrfinterm/master/fig/var_table.png)

You may setup your own variable mapping table in `./db/${MODEL_NAME}.csv` if you want to use other models.
**Any question, please open a GitHub [issue](https://github.com/lzhenn/cmip6-to-wrfinterm/issues). Have a short introduction of yourself (e.g. affiliation, research field, etc.) :-).**


