#!/usr/bin/env bash
# Creates the Python environment (venv/) once. Called by start.sh. Needs Python 3.9 - 3.12 and either internet (pip) or the wheelhouse/ folder.
set -euo pipefail
cd "$(dirname "$0")"
source ./config.sh
if [ -n "${PYTHON_MODULE}" ]; then
  if ! type module >/dev/null 2>&1; then for f in /etc/profile.d/lmod.sh /etc/profile.d/modules.sh /usr/share/lmod/lmod/init/bash; do if [ -f "$f" ]; then source "$f"; break; fi; done; fi
  module load ${PYTHON_MODULE}
fi
if [ -x venv/bin/python ] && venv/bin/python -c "import numpy, scipy, rasterio" 2>/dev/null; then echo "[setup] environment already exists"; exit 0; fi

PY=""
for c in python3.12 python3.11 python3.10 python3.9 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    v=$("$c" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
    case "$v" in 3.9|3.10|3.11|3.12) PY="$c"; break;; esac
  fi
done
if [ -z "$PY" ]; then
  echo "[setup] No Python 3.9-3.12 found (python3 is: $(python3 --version 2>&1 || echo none))."
  echo "[setup] Fix: run  module avail python  , choose a 3.9-3.12 version, put it in config.sh as PYTHON_MODULE=\"python/<version>\" and run start.sh again."
  exit 1
fi
echo "[setup] using $PY ($($PY --version))"
rm -rf venv; "$PY" -m venv venv
./venv/bin/python -m pip --version >/dev/null
if ./venv/bin/python -m pip install --quiet -r requirements.txt; then
  echo "[setup] installed from the internet"
elif [ -d wheelhouse ] && ./venv/bin/python -m pip install --quiet --no-index --find-links wheelhouse -r requirements.txt; then
  echo "[setup] installed from the offline wheelhouse/"
else
  echo "[setup] pip could not install the packages (no internet on this node and no usable wheelhouse/)."
  echo "[setup] Fix: run this script on a node with internet access, or tell the thesis author (the log above has the error)."
  exit 1
fi
./venv/bin/python -c "import numpy, scipy, rasterio; print('[setup] numpy', numpy.__version__, 'scipy', scipy.__version__, 'rasterio', rasterio.__version__)"
