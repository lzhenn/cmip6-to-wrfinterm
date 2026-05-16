#!/bin/bash
# Download minimal CESM2 CMIP6 data for cmip6-to-wrfinterm smoke test.
#
# Target period: 1990-01 (2 days for ETL test, monthly soil covers the month)
# Member: r11i1p1f1  Grid: gn  Scenario: historical
#
# Run on hqlx74:
#   bash sample/CESM2/download.sh
#
# Files land in:  sample/CESM2/
# After download: python3 run_c2w.py -m CESM2

set -e

OUTDIR="$(cd "$(dirname "$0")" && pwd)"
MEM=r11i1p1f1
GRID=gn
EXP=historical

# ESGF LLNL search endpoint (no login required for most CMIP6 data)
SEARCH="https://esgf-data.dkrz.de/esg-search/search"

echo "=== CESM2 CMIP6 minimal download ==="
echo "Output dir: ${OUTDIR}"
echo ""

# -----------------------------------------------------------------------
# Helper: search ESGF and return the first matching HTTP URL for a file
# -----------------------------------------------------------------------
esgf_url() {
    local variable=$1
    local table=$2
    # Returns JSON, grep for the direct download URL (httpserver)
    wget -q --timeout=120 -O - \
        "${SEARCH}?type=File&project=CMIP6&source_id=CESM2&experiment_id=${EXP}&member_id=${MEM}&variable=${variable}&table_id=${table}&format=application%2Fsolr%2Bjson&limit=5&fields=url" \
        | python3 -c "
import sys, json
data = json.load(sys.stdin)
docs = data.get('response',{}).get('docs',[])
for doc in docs:
    for u in doc.get('url',[]):
        if '|HTTPServer' in u:
            print(u.split('|')[0])
            sys.exit(0)
" 2>/dev/null
}

# -----------------------------------------------------------------------
# Download a file if not already present
# -----------------------------------------------------------------------
fetch() {
    local variable=$1
    local table=$2
    echo "--- Searching ESGF for ${variable} (${table}) ---"
    local url
    url=$(esgf_url "${variable}" "${table}")
    if [ -z "${url}" ]; then
        echo "WARNING: No URL found for ${variable}/${table}. Skipping."
        return
    fi
    local fname
    fname=$(basename "${url%%\?*}")
    if [ -f "${OUTDIR}/${fname}" ]; then
        echo "Already exists: ${fname}"
        return
    fi
    echo "Downloading: ${fname}"
    wget -q --show-progress -P "${OUTDIR}" "${url}" || \
        echo "ERROR: wget failed for ${url}"
}

# -----------------------------------------------------------------------
# Variables needed
# -----------------------------------------------------------------------
# 3-D hybrid levels (6hrLev)
fetch ta    6hrLev
fetch ua    6hrLev
fetch va    6hrLev
fetch hus   6hrLev
fetch ps    6hrLev

# Geopotential + sea-level pressure (6hrPlevPt)
fetch zg    6hrPlevPt
fetch psl   6hrPlevPt

# Near-surface (3hr)
fetch tas   3hr
fetch uas   3hr
fetch vas   3hr
fetch huss  3hr

# SST daily (day or Oday — check which is available for CESM2)
fetch tos   Oday || fetch ts day

# Soil monthly (Lmon)
fetch tsl   Lmon
fetch mrsos Lmon

echo ""
echo "=== Download complete. Files in ${OUTDIR} ==="
echo ""
echo "IMPORTANT: CESM2 CMIP6 files cover multi-year periods."
echo "config.CESM2.ini ETL window: 1990-01-01 to 1990-01-02."
echo "The code uses nearest-time selection so any file covering Jan 1990 is fine."
echo ""
echo "If ESGF search fails (network/SSL issues on hqlx74), get URLs manually:"
echo "  https://esgf-node.llnl.gov/search/cmip6/"
echo "  Filter: Source=CESM2, Experiment=historical, Member=r11i1p1f1"
echo "  Then: wget <url> -P ${OUTDIR}"
