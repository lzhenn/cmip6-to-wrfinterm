#!/usr/bin/env bash
# Fetch the real CESM2 SSP245 2-day smoke-test subset via OPeNDAP.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${REPO_ROOT}"
python3 sample/CESM2-ssp245/fetch_real.py "$@"
