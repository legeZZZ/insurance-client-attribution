"""Small application-facing facade for the Factor Registry."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .factor_registry import FactorRegistry


class FactorStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.registry = FactorRegistry(path)

    def register_factor(self, factor: Mapping[str, Any]):
        return self.registry.register_factor(factor)

    def ingest_evidence(self, evidence: Mapping[str, Any]):
        return self.registry.ingest_evidence(evidence)

    def ingest_factor_snapshot(self, snapshot: Mapping[str, Any]):
        return self.registry.ingest_factor_snapshot(snapshot)

    def retrieve(self, query: str = "", **filters: Any):
        return self.registry.retrieve_factor_candidates(query, **filters)

    def close(self) -> None:
        self.registry.close()


__all__ = ["FactorStore"]
