#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
code_dir=$(dirname "$script_dir")
wheel_dir=${1:-$code_dir/wheels}
builder_dir=$(mktemp -d "${TMPDIR:-/tmp}/stage-ef-wheels.XXXXXX")
trap 'rm -rf "$builder_dir"' EXIT HUP INT TERM
"${PYTHON_EXECUTABLE:-$code_dir/.venv/bin/python}" -m venv "$builder_dir/venv"
"$builder_dir/venv/bin/python" "$code_dir/tools/prepare_wheel_sources.py" "$code_dir/uv.lock" "$builder_dir/sources"
"$builder_dir/venv/bin/python" -m pip wheel --ignore-requires-python --no-deps -r "$builder_dir/sources/sources.txt" -w "$wheel_dir"
"$builder_dir/venv/bin/python" - "$wheel_dir" <<'PY'
import hashlib,json,platform,sys
from pathlib import Path
p=Path(sys.argv[1]);p.mkdir(parents=True,exist_ok=True)
(p/'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in sorted(p.glob('*.whl'))))
(p/'platform.json').write_text(json.dumps({'system':platform.system(),'machine':platform.machine(),'runtime':sys.version},indent=2))
PY
printf '%s\n' "已按锁文件构建并校验；在同平台使用 scripts/install_offline.sh $wheel_dir TARGET_VENV"
