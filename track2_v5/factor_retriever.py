"""Factor RAG retrieval and candidate-to-evidence joining."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .factor_store import FactorStore


def retrieve_factor_candidates(
    store: FactorStore,
    query: str = "",
    *,
    source_types: Sequence[str] = (),
    kinds: Sequence[str] = (),
    limit: int = 20,
    as_of: int | None = None,
    search_window: int | None = None,
) -> dict[str, Any]:
    items = store.retrieve(
        query,
        source_types=source_types,
        kinds=kinds,
        limit=limit,
        as_of=as_of,
        search_window=search_window,
    )
    return {
        "query": query,
        "candidate_count": len(items),
        "candidates": items,
        "claim_policy": "retrieval supplies candidates and evidence only; no causal conclusion",
    }


def attach_registry_context(
    candidates: Sequence[Mapping[str, Any]], store: FactorStore
) -> list[dict[str, Any]]:
    """Attach latest registry evidence without changing statistical results."""
    enriched = []
    for candidate in candidates:
        factor_id = str(candidate["factor_id"])
        records = store.retrieve(factor_id, limit=5)
        context = records[0] if records else {"factor_id": factor_id, "evidence": []}
        enriched.append({**dict(candidate), "registry_context": context})
    return enriched
