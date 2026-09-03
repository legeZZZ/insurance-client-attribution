"""Isolated public-data worker used by the Track 2 hidden benchmark."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict

from .track2_analysis import evaluate_public_dataset


def main() -> int:
    payload: Dict[str, Any] = json.load(sys.stdin)
    datasets = payload.get("datasets")
    if not isinstance(datasets, list):
        raise ValueError("payload.datasets must be a list")
    json.dump({"results": [evaluate_public_dataset(bundle) for bundle in datasets]}, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
