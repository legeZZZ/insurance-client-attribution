"""Configuration loading for Track 2 bundle execution."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any, Dict, Optional


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    if path is not None:
        return json.loads(path.read_text(encoding="utf-8"))
    resource = files("goai_control_tower").joinpath("config/default.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def resolve_output_dir(config: Dict[str, Any], value: Optional[str]) -> Path:
    return Path(value or config["runtime"]["output_dir"]).expanduser()


def validate_evidence_pack(pack: Dict[str, Any], config: Dict[str, Any]) -> None:
    policy = config.get("evidence", {})
    if policy.get("require_trace") and not pack.get("trace"):
        raise RuntimeError("evidence contract failed: trace is empty")
    if policy.get("require_artifacts") and not pack.get("artifacts"):
        raise RuntimeError("evidence contract failed: artifacts are empty")
    if policy.get("require_digests") and any(not item.get("content_digest") for item in pack.get("evidence", [])):
        raise RuntimeError("evidence contract failed: an evidence digest is missing")
