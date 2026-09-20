"""As-of registry snapshots to a future scan grid; never impute missing human data."""

from __future__ import annotations

from .contracts import digest
from .factor_registry import FactorRegistry


def registry_factors(path, *, days, as_of, window, existing):
    registry = FactorRegistry(path)
    try:
        factors = registry.retrieve_factor_candidates(
            "", as_of=as_of, search_window=window, limit=10000
        )
    finally:
        registry.close()
    used = {f["factor_id"] for f in existing}
    added, skipped = [], []
    for factor in factors:
        fid = factor["factor_id"]
        if fid in used:
            skipped.append({"factor_id": fid, "reason": "explicit_input_precedence"})
            continue
        snapshots = [
            s for s in factor["snapshots"] if s.get("scope_id", "global") == "global"
        ]
        values = {s["day"]: s["value"] for s in snapshots}
        if not all(d in values for d in days):
            skipped.append({"factor_id": fid, "reason": "incomplete_global_snapshots"})
            continue
        added.append(
            {
                "factor_id": fid,
                "days": days,
                "values": [values[d] for d in days],
                "kind": factor.get("metadata", {}).get("kind", "human_reported"),
                "source_type": factor["source_type"],
                "registry_digest": digest(factor),
            }
        )
    return added, {
        "as_of": as_of,
        "search_window": window,
        "added": [f["factor_id"] for f in added],
        "skipped": skipped,
        "snapshot_digest": digest(factors),
    }
