"""Immutable input/result freeze followed by a separately revealed five-table oracle."""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import digest
from .evaluation import normalize_result, score_predictions, validate_truth
from .hypothesis_registry import HypothesisRegistry


class BlindValidation:
    def __init__(self, db_path):
        self.registry = HypothesisRegistry(db_path)
        self.db = self.registry.db
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS blind_cases(id TEXT PRIMARY KEY, state TEXT NOT NULL, body TEXT NOT NULL)"
        )

    def close(self):
        self.registry.close()

    def read(self, *, case_id):
        row = self.db.execute(
            "SELECT state,body FROM blind_cases WHERE id=?", (case_id,)
        ).fetchone()
        if not row:
            raise KeyError(case_id)
        item = json.loads(row["body"])
        item["state"] = row["state"]
        return item

    def freeze(self, *, case_id, request, protocol):
        if not case_id or request.get("operation") not in {
            "pipeline",
            "association",
            "effect",
            "scan_window",
            "graph",
        }:
            raise ValueError(
                "nonempty case and allowlisted blind engine operation required"
            )
        if any(
            key in json.dumps(request).lower()
            for key in ("oracle_", "ground_truth", "changed_mechanisms")
        ):
            raise ValueError("oracle labels cannot enter blind engine request")
        if (
            not protocol.get("frozen_by")
            or not protocol.get("analysis_as_of")
            or not protocol.get("truth_scope") in {"full", "incremental_only"}
        ):
            raise ValueError("freeze owner, analysis time and truth scope required")
        item = {
            "case_id": case_id,
            "request": request,
            "request_digest": digest(request),
            "protocol": protocol,
            "protocol_digest": digest(protocol),
        }
        with self.registry.transaction():
            old = self.db.execute(
                "SELECT body FROM blind_cases WHERE id=?", (case_id,)
            ).fetchone()
            if old:
                old = json.loads(old[0])
                if (
                    old["request_digest"] != item["request_digest"]
                    or old["protocol_digest"] != item["protocol_digest"]
                ):
                    raise ValueError(
                        "frozen case cannot be replaced; use a new case id"
                    )
                return self.read(case_id=case_id)
            item["input_ref"] = self.registry._asset("data", request, [])
            self.db.execute(
                "INSERT INTO blind_cases VALUES (?, ?, ?)",
                (case_id, "INPUT_FROZEN", json.dumps(item)),
            )
            self.registry._audit("BLIND_INPUT_FROZEN", item)
        return self.read(case_id=case_id)

    def run(self, *, case_id):
        from .agent_orchestrator import run_pipeline
        from .association_discovery import discover_association_factors
        from .causal_discovery import discover_causal_graph
        from .quant_track import estimate_effect
        from .watchlist_scan import run_c_line

        with self.registry.transaction():
            item = self.read(case_id=case_id)
            if item["state"] in {"RESULT_FROZEN", "SCORED"}:
                return item
            if item["state"] != "INPUT_FROZEN":
                raise ValueError(
                    "blind run already consumed; inspect failed/interrupted run, do not rerun same case"
                )
            if digest(item["request"]) != item["request_digest"]:
                raise ValueError("frozen input digest mismatch")
            self.db.execute(
                "UPDATE blind_cases SET state='RUNNING' WHERE id=?", (case_id,)
            )
        operation = item["request"]["operation"]
        params = item["request"]["parameters"]
        try:
            if operation == "pipeline":
                result = run_pipeline(**params)
            elif operation == "association":
                result = discover_association_factors(**params)
            elif operation == "effect":
                result = estimate_effect(**params)
            elif operation == "graph":
                result = discover_causal_graph(**params)
            else:
                result = run_c_line(**params)
            predictions = normalize_result(result)
        except Exception as exc:  # noqa: BLE001 - retain failed runs in frozen evaluation
            result = {
                "execution_status": "FAILED",
                "reason": type(exc).__name__,
                "error": str(exc),
            }
            predictions = {}
        with self.registry.transaction():
            item.pop("state", None)
            item.update(
                result=result,
                predictions=predictions,
                result_digest=digest(result),
                prediction_digest=digest(predictions),
            )
            item["result_ref"] = self.registry._asset(
                "manifest",
                {"result": result, "predictions": predictions},
                [item["input_ref"]],
            )
            self.db.execute(
                "UPDATE blind_cases SET state=?,body=? WHERE id=?",
                ("RESULT_FROZEN", json.dumps(item), case_id),
            )
            self.registry._audit(
                "BLIND_RESULT_FROZEN",
                {"case_id": case_id, "result_ref": item["result_ref"]},
            )
        return self.read(case_id=case_id)

    def reveal(self, *, case_id, truth, reviewer, evidence_ref):
        validate_truth(truth)
        if not reviewer or not evidence_ref:
            raise ValueError(
                "independent truth review and business evidence reference required"
            )
        with self.registry.transaction():
            item = self.read(case_id=case_id)
            if reviewer == item["protocol"]["frozen_by"]:
                raise ValueError("truth reviewer must differ from freeze owner")
            if item["state"] == "SCORED":
                if item["truth_digest"] != digest(truth):
                    raise ValueError("revealed truth cannot be edited in place")
                return item
            if item["state"] != "RESULT_FROZEN":
                raise ValueError(
                    "freeze actual algorithm result before revealing truth"
                )
            if (
                digest(item["result"]) != item["result_digest"]
                or digest(item["predictions"]) != item["prediction_digest"]
            ):
                raise ValueError("frozen result was changed")
            scores = score_predictions(item["predictions"], truth)
            item.pop("state", None)
            item.update(
                truth=truth,
                truth_digest=digest(truth),
                scores=scores,
                reviewer=reviewer,
                evidence_ref=evidence_ref,
            )
            item["truth_ref"] = self.registry._asset(
                "manifest",
                {"truth": truth, "reviewer": reviewer, "evidence_ref": evidence_ref},
                [item["result_ref"]],
            )
            self.db.execute(
                "UPDATE blind_cases SET state=?,body=? WHERE id=?",
                ("SCORED", json.dumps(item), case_id),
            )
            self.registry._audit(
                "BLIND_SCORED", {"case_id": case_id, "truth_ref": item["truth_ref"]}
            )
        return self.read(case_id=case_id)

    def report(self, *, case_id, output_path):
        item = self.read(case_id=case_id)
        if item["state"] != "SCORED":
            raise ValueError("truth not yet revealed")
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = f"# 盲测 {case_id}\n\n输入、结果和事后真值分别冻结。\n\n状态：{item['state']}\n\n输入摘要：{item['request_digest']}\n\n结果摘要：{item['result_digest']}\n\n真值范围：{item['protocol']['truth_scope']}\n\n```json\n{json.dumps(item['scores'], ensure_ascii=False, indent=2)}\n```\n"
        path.write_text(text)
        return {"path": str(path.resolve()), "case_id": case_id, "status": "SCORED"}


def execute_blind(*, db_path, action, parameters):
    service = BlindValidation(db_path)
    try:
        if action not in {"freeze", "run", "reveal", "read", "report"}:
            raise ValueError("unsupported blind action")
        return getattr(service, action)(**parameters)
    finally:
        service.close()
