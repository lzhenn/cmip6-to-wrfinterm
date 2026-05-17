# CESM2 SSP245 Smoke Test

This sample fetches a real 2-day CMIP6 ScenarioMIP CESM2 SSP245 subset
(`2015-01-01_00` through `2015-01-02_00`, ensemble `r11i1p1f1`) from UCAR
ESGF via OPeNDAP.

```bash
# From the repository root:
conda activate test_c2w
bash sample/CESM2-ssp245/download.sh
python3 run_c2w.py -m CESM2-ssp245
```

The converter writes:

```text
output/CESM2:2015-01-01_00 ... output/CESM2:2015-01-02_00
output/CESM2_SST:2015-01-01_00 ... output/CESM2_SST:2015-01-02_00
```

For WPS/WRF, copy `namelist.wps` to your WPS directory and `namelist.input`
to your WRF `run/` directory. Link both prefixes before running `metgrid.exe`:

```bash
ln -sf /path/to/cmip6-to-wrfinterm/output/CESM2:*     /path/to/WPS/
ln -sf /path/to/cmip6-to-wrfinterm/output/CESM2_SST:* /path/to/WPS/
```

The public CESM2 SSP245 holdings are sparse. `6hrLev` exists only for a small
set of variables (`ta`, `ua`, `va`, `hus`, `ps`) and variants (`r2i1p1f1`,
`r11i1p1f1`). This sample uses `r11i1p1f1`. CESM2 SSP245 does not publish
`uas`/`vas`, so `real.exe` will report that it replaces missing surface winds
with the closest model level; this is expected for this sample.
