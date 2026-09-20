#!/bin/sh
set -eu
if [ "$#" -ne 2 ]; then echo 'usage: install_offline.sh WHEELHOUSE TARGET_VENV' >&2; exit 2; fi
"${PYTHON_EXECUTABLE:-python3}" - "$1" <<'PY'
from pathlib import Path
import hashlib,sys
folder=Path(sys.argv[1]);expected={}
for line in (folder/'SHA256SUMS').read_text().splitlines():
    checksum,name=line.split('  ',1)
    if Path(name).name!=name or not name.endswith('.whl'): raise ValueError('invalid wheel manifest')
    expected[name]=checksum
if set(expected)!={p.name for p in folder.glob('*.whl')}: raise ValueError('wheel set differs from frozen manifest')
for name,checksum in expected.items():
    if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=checksum: raise ValueError('wheel digest mismatch: '+name)
print('Verified',len(expected),'offline wheels')
PY
"${PYTHON_EXECUTABLE:-python3}" -m venv "$2"
"$2/bin/python" -m pip install --ignore-requires-python --no-deps --no-index "$1"/*.whl
"$2/bin/python" -m pip check
