"""Dataset provenance catalog for Track 2 training and evaluation."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, Dict


def load_dataset_catalog() -> Dict[str, Any]:
    path = resources.files("goai_control_tower").joinpath("datasets/track2_catalog.json")
    catalog = json.loads(path.read_text(encoding="utf-8"))
    required = {"dataset_id", "name", "official_url", "license", "license_status", "recommended_use", "limitations"}
    for dataset in catalog.get("datasets", []):
        missing = required - set(dataset)
        if missing:
            raise ValueError("dataset catalog entry is missing fields: " + ", ".join(sorted(missing)))
    return catalog
