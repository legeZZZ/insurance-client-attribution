"""Configuration loading for attribution bundle execution."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any


def load_config(path: Path | None = None) -> dict[str, Any]:
    if path is not None:
        return json.loads(path.read_text(encoding="utf-8"))
    resource = files("runtime").joinpath("config/default.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def resolve_output_dir(config: dict[str, Any], value: str | None) -> Path:
    return Path(value or config["runtime"]["output_dir"]).expanduser()


def validate_evidence_pack(pack: dict[str, Any], config: dict[str, Any]) -> None:
    policy = config.get("evidence", {})
    if policy.get("require_trace") and not pack.get("trace"):
        raise RuntimeError("evidence contract failed: trace is empty")
    if policy.get("require_artifacts") and not pack.get("artifacts"):
        raise RuntimeError("evidence contract failed: artifacts are empty")
    if policy.get("require_digests") and any(
        not item.get("content_digest") for item in pack.get("evidence", [])
    ):
        raise RuntimeError("evidence contract failed: an evidence digest is missing")
