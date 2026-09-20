"""Fresh-process executable method replay and bound JSON handoffs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .contracts import digest, finite

OPS = {"check_metric", "check_overlap", "estimate_effect", "scan_window"}


def isolated_replay(operation, request, binding, *, timeout=30):
    if operation not in OPS or not 0 < finite(timeout, "timeout") <= 60:
        raise ValueError("invalid operation or bounded timeout")
    job = {"operation": operation, "request": request, "binding": binding}
    raw = json.dumps(job, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("skill replay exceeds input budget")
    env = {
        k: os.environ[k] for k in ("PATH", "TMPDIR", "SYSTEMROOT") if k in os.environ
    }
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    start = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, "-I", str(Path(__file__).with_name("skill_worker.py"))],
            input=raw,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("skill replay exceeded total deadline") from exc
    if result.returncode or len(result.stdout) > 32 * 1024 * 1024:
        raise ValueError("skill worker failed or output exceeded limit")
    report = json.loads(result.stdout)
    if (
        report.get("binding") != binding
        or report.get("input_digest") != digest(request)
        or report.get("operation") != operation
        or report.get("digest")
        != digest({k: v for k, v in report.items() if k != "digest"})
    ):
        raise ValueError("skill replay handoff binding mismatch")
    report["cost"] = {
        "input_bytes": len(raw),
        "output_bytes": len(result.stdout),
        "elapsed_seconds": time.monotonic() - start,
        "model_tokens": 0,
    }
    report["worker_digest"] = report["digest"]
    report["digest"] = digest({k: v for k, v in report.items() if k != "digest"})
    return report
