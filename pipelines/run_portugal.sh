#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -e .

python scripts/download_nuts3.py --country portugal

echo "=== Grid info ==="
climate-risk grid-info --config config/pilot_portugal.yaml

echo "=== Running Portugal pilot (all hazards) ==="
climate-risk run-pilot --config config/pilot_portugal.yaml "$@"
