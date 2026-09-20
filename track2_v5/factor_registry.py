"""Structured Factor Registry and evidence store.

This is the first implementation of the Factor RAG contract.  Retrieval is
hybrid by design: structured filters decide what is eligible, while SQLite
FTS5 only helps match names, aliases and descriptions.  The store supplies
evidence and validation context; it never writes a causal conclusion.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import digest, finite, integer, validate_contract


def _json(value: Any) -> str:
    return json.dumps(
        value if value is not None else {}, ensure_ascii=False, sort_keys=True
    )


def _digest(value: Any) -> str:
    return digest(value)


class FactorRegistry:
    """SQLite-backed registry with provenance and time-series snapshots."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._batch = False
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _commit(self):
        if not self._batch:
            self.connection.commit()

    @staticmethod
    def _validate_version(body):
        digest(dict(body))
        registered = body.get("factor_contract") or body.get("metadata", {}).get(
            "factor_contract"
        )
        if registered:
            available = body.get(
                "available_day", body.get("metadata", {}).get("available_day")
            )
            if available is None:
                raise ValueError("registered factor contract requires availability")
            contract = {
                k: v
                for k, v in registered.items()
                if k not in {"digest", "schema_version"}
            }
            if contract.get("factor_id") != body["factor_id"]:
                raise ValueError("factor contract identity mismatch")
            contract.update(available_at=available, as_of=available)
            validate_contract("FactorContract", contract)
        for key in ("available_day", "search_window"):
            value = body.get(key, body.get("metadata", {}).get(key))
            if value is not None:
                integer(value, key)

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS factor_versions (
              kind TEXT NOT NULL, logical_key TEXT NOT NULL, version INTEGER NOT NULL,
              factor_id TEXT NOT NULL, body TEXT NOT NULL, digest TEXT NOT NULL,
              available_day INTEGER, search_window INTEGER,
              PRIMARY KEY(kind,logical_key,version));
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
        self._commit()

    def register_factor(self, factor: Mapping[str, Any]) -> dict[str, Any]:
        self._validate_version(factor)
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
        self._version("factor", factor_id, dict(factor))
        self._commit()
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
        self._validate_version(evidence)
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
        self._version(
            "evidence", evidence_id, {**dict(evidence), "evidence_id": evidence_id}
        )
        self._commit()
        return {"evidence_id": evidence_id, **dict(evidence)}

    def ingest_factor_snapshot(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        self._validate_version(snapshot)
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
                integer(snapshot["day"], "day"),
                finite(snapshot["value"], "snapshot value"),
                snapshot.get("source_uri"),
                snapshot.get("content_digest"),
                snapshot.get("license_ref"),
                _json(snapshot.get("metadata", {})),
            ),
        )
        self._version(
            "snapshot",
            _json([factor_id, snapshot.get("scope_id", "global"), snapshot["day"]]),
            dict(snapshot),
        )
        self._commit()
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
        as_of: int | None = None,
        search_window: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return eligible factors with provenance, evidence and snapshots."""
        if as_of is not None:
            return self._retrieve_as_of(
                query,
                source_types=source_types,
                kinds=kinds,
                limit=limit,
                as_of=as_of,
                search_window=search_window,
            )
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
        sql += " AND f.status = 'active' ORDER BY f.updated_at DESC"
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
            fallback_sql += " AND f.status = 'active' ORDER BY f.updated_at DESC"
            rows = self.connection.execute(fallback_sql, fallback_params).fetchall()
        result = []
        for row in rows:
            item = self._factor_row(row)
            if item.get("metadata", {}).get("search_window") is not None:
                continue  # A queued intake requires explicit governed as-of retrieval.
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
        return result[: max(1, int(limit))]

    def _version(self, kind, key, body):
        metadata = body.get("metadata", {})
        available = body.get("available_day", metadata.get("available_day"))
        window = body.get("search_window", metadata.get("search_window"))
        if available is not None:
            available = integer(available, "available_day")
        if window is not None:
            window = integer(window, "search_window")
        fingerprint = digest(body)
        old = self.connection.execute(
            "SELECT version,digest FROM factor_versions WHERE kind=? AND logical_key=? ORDER BY version DESC LIMIT 1",
            (kind, key),
        ).fetchone()
        if old and old["digest"] == fingerprint:
            return
        self.connection.execute(
            "INSERT INTO factor_versions VALUES (?,?,?,?,?,?,?,?)",
            (
                kind,
                key,
                old["version"] + 1 if old else 1,
                body["factor_id"],
                _json(body),
                fingerprint,
                available,
                window,
            ),
        )

    def history(self, factor_id):
        return [
            {**dict(r), "body": json.loads(r["body"])}
            for r in self.connection.execute(
                "SELECT * FROM factor_versions WHERE factor_id=? ORDER BY kind,logical_key,version",
                (factor_id,),
            )
        ]

    def intake_next_window(
        self, factor, *, evidence=(), snapshots=(), current_window, available_day
    ):
        """Manual/external intake cannot enter an already frozen investigation."""
        window = integer(current_window, "current_window") + 1
        available_day = integer(available_day, "available_day")
        fid = factor["factor_id"]
        if not factor.get("source_type") or not factor.get("license_ref"):
            raise ValueError("declared source and license required")
        for item in [*evidence, *snapshots]:
            if (
                item.get("factor_id") != fid
                or not item.get("license_ref")
                or not item.get("source_uri")
            ):
                raise ValueError(
                    "intake evidence requires matching factor, declared source and license"
                )
        # All validation precedes writes. No provenance investigation is performed.
        for item in snapshots:
            integer(item["day"], "day")
            finite(item["value"], "value")

        def stamp(item):
            return {
                **dict(item),
                "available_day": available_day,
                "search_window": window,
                "metadata": {
                    **item.get("metadata", {}),
                    "available_day": available_day,
                    "search_window": window,
                },
            }

        try:
            self._batch = True
            with self.connection:
                self.register_factor(stamp(factor))
                for item in evidence:
                    self.ingest_evidence(stamp(item))
                for item in snapshots:
                    self.ingest_factor_snapshot(stamp(item))
        finally:
            self._batch = False
        return {
            "factor_id": fid,
            "eligible_from_window": window,
            "available_day": available_day,
            "claim_ceiling": "CANDIDATE_ASSOCIATION",
        }

    def _retrieve_as_of(
        self, query, *, source_types, kinds, limit, as_of, search_window
    ):
        as_of = integer(as_of, "as_of")
        if search_window is None:
            raise ValueError("governed retrieval requires a search window")
        search_window = integer(search_window, "search_window")
        latest = {}
        for row in self.connection.execute(
            "SELECT * FROM factor_versions WHERE available_day<=? AND search_window<=? ORDER BY version",
            (as_of, search_window),
        ):
            latest[(row["kind"], row["logical_key"])] = dict(row)
        factors = [v for (kind, _), v in latest.items() if kind == "factor"]
        result = []
        for version in sorted(factors, key=lambda r: r["factor_id"]):
            item = json.loads(version["body"])
            if (
                item.get("status", "active") != "active"
                or (source_types and item.get("source_type") not in source_types)
                or (kinds and item.get("metadata", {}).get("kind") not in kinds)
            ):
                continue
            search = " ".join(
                [
                    item["factor_id"],
                    item.get("name", ""),
                    item.get("description", ""),
                    *item.get("aliases", []),
                ]
            ).casefold()
            if query.strip().casefold() not in search:
                continue
            fid = item["factor_id"]
            related = [
                (kind, row)
                for (kind, _), row in latest.items()
                if row["factor_id"] == fid
            ]
            item["evidence"] = [
                {
                    **json.loads(r["body"]),
                    "version": r["version"],
                    "registry_digest": r["digest"],
                }
                for k, r in related
                if k == "evidence"
            ]
            item["snapshots"] = [
                {
                    **json.loads(r["body"]),
                    "version": r["version"],
                    "registry_digest": r["digest"],
                }
                for k, r in related
                if k == "snapshot" and json.loads(r["body"])["day"] <= as_of
            ]
            registered = item.get("metadata", {}).get("factor_contract") or item.get(
                "factor_contract"
            )
            item["factor_contract"] = None
            if registered:
                contract = {
                    k: v
                    for k, v in registered.items()
                    if k not in {"digest", "schema_version"}
                }
                if contract.get("factor_id") != fid:
                    raise ValueError("factor contract identity mismatch")
                contract.update(available_at=version["available_day"], as_of=as_of)
                item["factor_contract"] = validate_contract("FactorContract", contract)
            item.update(
                version=version["version"],
                registry_digest=version["digest"],
                as_of=as_of,
                search_window=search_window,
                claim_ceiling="CANDIDATE_ASSOCIATION",
                posterior_probability=None,
                causal_eligible=False,
            )
            item["production_eligible"] = bool(
                item.get("license_ref")
                and item["evidence"]
                and all(
                    e.get("license_ref") for e in item["evidence"] + item["snapshots"]
                )
            )
            result.append(item)
        return result[: max(1, integer(limit, "limit"))]

    def export_window(self, registry, *, name, as_of, search_window, query=""):
        candidates = self.retrieve_factor_candidates(
            query, as_of=as_of, search_window=search_window, limit=100000
        )
        # A revised export invalidates statistics, claims and skills downstream.
        return registry.revise_resource(
            name,
            {"as_of": as_of, "search_window": search_window, "candidates": candidates},
            kind="snapshot",
        )

    def close(self) -> None:
        self.connection.close()


__all__ = ["FactorRegistry"]
