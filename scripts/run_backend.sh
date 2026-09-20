#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
code_dir=$(dirname "$script_dir")
exec "${PYTHON_EXECUTABLE:-$code_dir/.venv/bin/python}" "$code_dir/tools/run_causal_pipeline.py" "$@"
