"""Structured Factor Registry and evidence store.

This is the first implementation of the Factor RAG contract.  Retrieval is
hybrid by design: structured filters decide what is eligible, while SQLite
FTS5 only helps match names, aliases and descriptions.  The store supplies
evidence and validation context; it never writes a causal conclusion.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _json(value: Any) -> str:
    return json.dumps(
        value if value is not None else {}, ensure_ascii=False, sort_keys=True
    )


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()[:16]


class FactorRegistry:
    """SQLite-backed registry with provenance and time-series snapshots."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS factors (
              factor_id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              source_type TEXT NOT NULL,
              scope TEXT NOT NULL DEFAULT '{}',
              aliases TEXT NOT NULL DEFAULT '[]',
              status TEXT NOT NULL DEFAULT 'active',
              license_ref TEXT,
              valid_from TEXT,
              valid_to TEXT,
              metadata TEXT NOT NULL DEFAULT '{}',
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence (
              evidence_id TEXT PRIMARY KEY,
              factor_id TEXT NOT NULL REFERENCES factors(factor_id),
              evidence_type TEXT NOT NULL,
              source_uri TEXT,
              observed_at TEXT,
              excerpt TEXT NOT NULL DEFAULT '',
              content_digest TEXT,
              license_ref TEXT,
              metadata TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS snapshots (
              snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
              factor_id TEXT NOT NULL REFERENCES factors(factor_id),
              scope_id TEXT NOT NULL DEFAULT 'global',
              day INTEGER NOT NULL,
              value REAL NOT NULL,
              source_uri TEXT,
              content_digest TEXT,
              license_ref TEXT,
              metadata TEXT NOT NULL DEFAULT '{}',
              UNIQUE(factor_id, scope_id, day)
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS factor_fts USING fts5(
              factor_id UNINDEXED, name, description, aliases
            );
            """
        )
        self.connection.commit()

    def register_factor(self, factor: Mapping[str, Any]) -> dict[str, Any]:
        factor_id = str(factor["factor_id"])
        name = str(factor.get("name", factor_id))
        aliases = [str(value) for value in factor.get("aliases", [])]
        now = datetime.now(UTC).isoformat(timespec="seconds")
        self.connection.execute(
            """INSERT INTO factors
               (factor_id, name, description, source_type, scope, aliases, status,
                license_ref, valid_from, valid_to, metadata, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(factor_id) DO UPDATE SET
                 name=excluded.name, description=excluded.description,
                 source_type=excluded.source_type, scope=excluded.scope,
                 aliases=excluded.aliases, status=excluded.status,
                 license_ref=excluded.license_ref, valid_from=excluded.valid_from,
                 valid_to=excluded.valid_to, metadata=excluded.metadata,
                 updated_at=excluded.updated_at""",
            (
                factor_id,
                name,
                str(factor.get("description", "")),
                str(factor.get("source_type", "unknown")),
                _json(factor.get("scope", {})),
                _json(aliases),
                str(factor.get("status", "active")),
                factor.get("license_ref"),
                factor.get("valid_from"),
                factor.get("valid_to"),
                _json(factor.get("metadata", {})),
                now,
            ),
        )
        self.connection.execute(
            "DELETE FROM factor_fts WHERE factor_id = ?", (factor_id,)
        )
        self.connection.execute(
            "INSERT INTO factor_fts(factor_id, name, description, aliases) VALUES (?, ?, ?, ?)",
            (factor_id, name, str(factor.get("description", "")), " ".join(aliases)),
        )
        self.connection.commit()
        return self.get_factor(factor_id) or {"factor_id": factor_id}

    def get_factor(self, factor_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM factors WHERE factor_id = ?", (str(factor_id),)
        ).fetchone()
        return self._factor_row(row) if row else None

    def _factor_row(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        for field in ("scope", "aliases", "metadata"):
            item[field] = json.loads(item[field])
        return item

    def ingest_evidence(self, evidence: Mapping[str, Any]) -> dict[str, Any]:
        factor_id = str(evidence["factor_id"])
        if self.get_factor(factor_id) is None:
            raise KeyError(f"factor is not registered: {factor_id}")
        evidence_id = str(evidence.get("evidence_id") or _digest(evidence))
        now = datetime.now(UTC).isoformat(timespec="seconds")
        self.connection.execute(
            """INSERT OR REPLACE INTO evidence
               (evidence_id, factor_id, evidence_type, source_uri, observed_at,
                excerpt, content_digest, license_ref, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                evidence_id,
                factor_id,
                str(evidence.get("evidence_type", "observation")),
                evidence.get("source_uri"),
                evidence.get("observed_at"),
                str(evidence.get("excerpt", "")),
                evidence.get("content_digest"),
                evidence.get("license_ref"),
                _json(evidence.get("metadata", {})),
                now,
            ),
        )
        self.connection.commit()
        return {"evidence_id": evidence_id, **dict(evidence)}

    def ingest_factor_snapshot(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        factor_id = str(snapshot["factor_id"])
        if self.get_factor(factor_id) is None:
            raise KeyError(f"factor is not registered: {factor_id}")
        self.connection.execute(
            """INSERT INTO snapshots
               (factor_id, scope_id, day, value, source_uri, content_digest,
                license_ref, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(factor_id, scope_id, day) DO UPDATE SET
                 value=excluded.value, source_uri=excluded.source_uri,
                 content_digest=excluded.content_digest, license_ref=excluded.license_ref,
                 metadata=excluded.metadata""",
            (
                factor_id,
                str(snapshot.get("scope_id", "global")),
                int(snapshot["day"]),
                float(snapshot["value"]),
                snapshot.get("source_uri"),
                snapshot.get("content_digest"),
                snapshot.get("license_ref"),
                _json(snapshot.get("metadata", {})),
            ),
        )
        self.connection.commit()
        return dict(snapshot)

    def evidence_for(self, factor_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM evidence WHERE factor_id = ? ORDER BY observed_at, evidence_id",
            (str(factor_id),),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"])
            result.append(item)
        return result

    def snapshots_for(
        self, factor_id: str, scope_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM snapshots WHERE factor_id = ?"
        params: list[Any] = [str(factor_id)]
        if scope_id is not None:
            query += " AND scope_id = ?"
            params.append(str(scope_id))
        query += " ORDER BY day"
        return [dict(row) for row in self.connection.execute(query, params).fetchall()]

    def retrieve_factor_candidates(
        self,
        query: str = "",
        *,
        source_types: Sequence[str] = (),
        kinds: Sequence[str] = (),
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return eligible factors with provenance, evidence and snapshots."""
        params: list[Any] = []
        if query.strip():
            sql = (
                "SELECT f.* FROM factor_fts s JOIN factors f ON f.factor_id=s.factor_id "
                "WHERE factor_fts MATCH ?"
            )
            params.append(query.strip())
        else:
            sql = "SELECT f.* FROM factors f WHERE 1=1"
        if source_types:
            sql += " AND f.source_type IN (" + ",".join("?" for _ in source_types) + ")"
            params.extend(source_types)
        if kinds:
            # Kind is metadata in this minimal store; filter is applied below.
            pass
        sql += " ORDER BY f.updated_at DESC LIMIT ?"
        params.append(max(1, int(limit)))
        try:
            rows = self.connection.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            # FTS syntax errors (for example punctuation in a user query)
            # fall through to the literal, non-tokenizing lookup below.
            rows = []
        # FTS5 tokenization is intentionally conservative for short Chinese
        # queries and exact IDs.  LIKE is the deterministic fallback, still
        # bounded by the same structured filters and limit.
        if query.strip() and not rows:
            like = f"%{query.strip()}%"
            fallback_sql = (
                "SELECT f.* FROM factors f WHERE "
                "(f.factor_id LIKE ? OR f.name LIKE ? OR f.description LIKE ? OR f.aliases LIKE ?)"
            )
            fallback_params: list[Any] = [like, like, like, like]
            if source_types:
                fallback_sql += (
                    " AND f.source_type IN ("
                    + ",".join("?" for _ in source_types)
                    + ")"
                )
                fallback_params.extend(source_types)
            fallback_sql += " ORDER BY f.updated_at DESC LIMIT ?"
            fallback_params.append(max(1, int(limit)))
            rows = self.connection.execute(fallback_sql, fallback_params).fetchall()
        result = []
        for row in rows:
            item = self._factor_row(row)
            if kinds and str(item.get("metadata", {}).get("kind")) not in {
                str(k) for k in kinds
            }:
                continue
            item["evidence"] = self.evidence_for(item["factor_id"])
            item["snapshots"] = self.snapshots_for(item["factor_id"])
            item["production_eligible"] = bool(
                item.get("license_ref")
                and item["evidence"]
                and all(evidence.get("license_ref") for evidence in item["evidence"])
            )
            item["eligibility_reason"] = (
                "source_and_evidence_license_present"
                if item["production_eligible"]
                else "missing_factor_or_evidence_license"
            )
            item["retrieval_basis"] = "structured_filter+fts5+provenance"
            result.append(item)
        return result

    def close(self) -> None:
        self.connection.close()


__all__ = ["FactorRegistry"]
