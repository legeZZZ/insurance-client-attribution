"""Persistent C-line coordinator: leased runs, watermarks, feedback and skill reuse."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from .contracts import digest, finite, integer
from .hypothesis_registry import HypothesisRegistry
from .skill_governance import SkillGovernance, isolated_replay


class ScanService:
    def __init__(self, path):
        self.registry = HypothesisRegistry(path)
        self.db = self.registry.db
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS scan_daemons(job TEXT PRIMARY KEY,pid INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS scan_jobs(name TEXT PRIMARY KEY, config TEXT NOT NULL, enabled INTEGER NOT NULL, watermark INTEGER, next_due REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS scan_runs(id TEXT PRIMARY KEY, job TEXT NOT NULL, window INTEGER NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS scan_alerts(id TEXT PRIMARY KEY, job TEXT NOT NULL, window INTEGER NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS scan_confirmations(job TEXT NOT NULL, window_start INTEGER NOT NULL, window_end INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(job,window_start,window_end));
        """)

    def close(self):
        self.registry.close()

    def configure(
        self,
        *,
        name,
        input_path,
        interval_seconds=60,
        max_staleness_seconds=3600,
        test_budget=200,
        lifetime_test_budget=100000,
        timeout=30,
        error_policy="exploratory_only",
        total_alpha=0.05,
        skill_name=None,
        skill_context=None,
        factor_db_path=None,
    ):
        if (
            not name
            or not 0 < finite(interval_seconds, "interval") <= 86400
            or not 0 < finite(timeout, "timeout") <= 60
            or finite(max_staleness_seconds, "freshness") <= 0
        ):
            raise ValueError("bounded schedule, freshness and timeout required")
        if (
            integer(test_budget, "test_budget") < 1
            or integer(lifetime_test_budget, "lifetime_test_budget") < test_budget
            or error_policy not in {"exploratory_only", "alpha_spending_empirical"}
            or not 0 < finite(total_alpha, "total_alpha") < 1
        ):
            raise ValueError("invalid lifetime test/error policy")
        config = {
            "input_path": str(Path(input_path).resolve()),
            "interval_seconds": interval_seconds,
            "max_staleness_seconds": max_staleness_seconds,
            "test_budget": test_budget,
            "lifetime_test_budget": lifetime_test_budget,
            "timeout": timeout,
            "error_policy": error_policy,
            "total_alpha": total_alpha,
            "skill_name": skill_name,
            "skill_context": skill_context or {},
        }
        if factor_db_path is not None:
            config["factor_db_path"] = str(Path(factor_db_path).resolve())
        with self.registry.transaction():
            for other in self.db.execute(
                "SELECT name,config FROM scan_jobs WHERE name!=?", (name,)
            ):
                if json.loads(other["config"])["input_path"] == config["input_path"]:
                    raise ValueError(
                        "same named source cannot reset cross-time policy under another job name"
                    )
            old = self.db.execute(
                "SELECT config FROM scan_jobs WHERE name=?", (name,)
            ).fetchone()
            if old and json.loads(old[0]) != config:
                raise ValueError(
                    "schedule config is frozen; do not reset an existing job/error budget"
                )
            self.db.execute(
                "INSERT OR IGNORE INTO scan_jobs VALUES (?,?,0,NULL,0)",
                (name, json.dumps(config)),
            )
            self.registry._audit("SCAN_CONFIGURED", {"name": name, **config})
        return self.status(name)

    def launch(self, name):
        import subprocess
        import sys

        self.start(name)
        with self.registry.transaction():
            old = self.db.execute(
                "SELECT pid FROM scan_daemons WHERE job=?", (name,)
            ).fetchone()
            if old:
                try:
                    os.kill(old[0], 0)
                    return {"status": "ALREADY_RUNNING", "pid": old[0]}
                except ProcessLookupError:
                    pass
            log_path = Path(self.registry.path).with_name(
                "scan-worker-" + digest(name).split(":")[-1][:12] + ".log"
            )
            with log_path.open("ab") as log:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-I",
                        str(Path(__file__).with_name("scan_worker.py")),
                        "--db",
                        str(Path(self.registry.path).resolve()),
                        "--job",
                        name,
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    start_new_session=True,
                )
            self.db.execute(
                "INSERT INTO scan_daemons VALUES (?,?) ON CONFLICT(job) DO UPDATE SET pid=excluded.pid",
                (name, process.pid),
            )
            self.registry._audit(
                "SCAN_WORKER_LAUNCHED", {"job": name, "pid": process.pid}
            )
        return {"status": "RUNNING", "pid": process.pid, "log_path": str(log_path)}

    def start(self, name):
        with self.registry.transaction():
            if (
                self.db.execute(
                    "UPDATE scan_jobs SET enabled=1 WHERE name=?", (name,)
                ).rowcount
                != 1
            ):
                raise KeyError(name)
            self.registry._audit("SCAN_STARTED", {"name": name})
        return self.status(name)

    def stop(self, name):
        with self.registry.transaction():
            if (
                self.db.execute(
                    "UPDATE scan_jobs SET enabled=0 WHERE name=?", (name,)
                ).rowcount
                != 1
            ):
                raise KeyError(name)
            self.registry._audit("SCAN_STOPPED", {"name": name})
        return self.status(name)

    def status(self, name):
        row = self.db.execute(
            "SELECT * FROM scan_jobs WHERE name=?", (name,)
        ).fetchone()
        if not row:
            raise KeyError(name)
        return {
            **dict(row),
            "config": json.loads(row["config"]),
            "runs": [
                {
                    "id": r["id"],
                    "status": r["status"],
                    "window": r["window"],
                    "body": json.loads(r["body"]),
                }
                for r in self.db.execute(
                    "SELECT * FROM scan_runs WHERE job=? ORDER BY rowid", (name,)
                )
            ],
        }

    def recover(self):
        recovered = []
        for row in self.db.execute(
            "SELECT * FROM scan_runs WHERE status='RUNNING'"
        ).fetchall():
            body = json.loads(row["body"])
            alive = True
            try:
                os.kill(body["owner_pid"], 0)
            except ProcessLookupError:
                alive = False
            if body["lease_until"] > time.time() and alive:
                continue
            body.update(error="interrupted_or_expired", reason_codes=["DATA_INVALID"])
            with self.registry.transaction():
                self.db.execute(
                    "UPDATE scan_runs SET status='INTERRUPTED',body=? WHERE id=? AND status='RUNNING'",
                    (json.dumps(body), row["id"]),
                )
                self.registry._audit(
                    "SCAN_RECOVERED",
                    {
                        "run_id": row["id"],
                        "tests_reserved_remain_spent": body["tests_charged"],
                    },
                )
            recovered.append(row["id"])
        return {"recovered": recovered}

    def tick(self, name, *, force=False):
        self.recover()
        job = self.status(name)
        config = job["config"]
        now = time.time()
        if not job["enabled"]:
            return {"status": "STOPPED"}
        if not force and now < job["next_due"]:
            return {"status": "NOT_DUE"}
        path = Path(config["input_path"])
        if (
            not path.is_file()
            or now - path.stat().st_mtime > config["max_staleness_seconds"]
        ):
            with self.registry.transaction():
                self.db.execute(
                    "UPDATE scan_jobs SET next_due=? WHERE name=?",
                    (now + config["interval_seconds"], name),
                )
            self._event("SCAN_STALE", {"name": name})
            return {"status": "STALE", "reason_codes": ["DATA_INVALID"]}
        payload = json.loads(path.read_text())
        window = integer(payload["window_id"], "window_id")
        request = dict(payload["request"])
        if (
            not request.get("days")
            or max(request["days"]) < payload["expected_through"]
            or max(request["days"]) > payload["observed_through"]
        ):
            return {"status": "STALE", "reason_codes": ["DATA_INVALID"]}
        raw_input_digest = digest(payload)
        if any(r["status"] == "RUNNING" and r["window"] == window for r in job["runs"]):
            return {"status": "BUSY"}
        completed = next(
            (
                r
                for r in reversed(job["runs"])
                if r["window"] == window and r["status"] == "COMPLETED"
            ),
            None,
        )
        if completed and completed["body"].get("raw_input_digest") == raw_input_digest:
            return {"status": "ALREADY_PROCESSED", "corrected": False}
        registry_intake = None
        if config.get("factor_db_path"):
            from .scan_factor_bridge import registry_factors

            added, registry_intake = registry_factors(
                config["factor_db_path"],
                days=request["days"],
                as_of=integer(payload["observed_through"], "observed_through"),
                window=window,
                existing=request["factors"],
            )
            request["factors"] = [*request["factors"], *added]
        request["test_budget"] = config["test_budget"]
        request["window_id"] = str(window)
        from .feedback_service import FeedbackService

        feedback = FeedbackService(self.registry.path)
        try:
            request["budget_multipliers"] = feedback.calibration()
        finally:
            feedback.close()
        source = self.registry.revise_resource(
            "scan:" + name + ":" + str(window), request
        )
        # Corrected old windows invalidate their alerts; they are never silently re-alerted.
        if job["watermark"] is not None and window <= job["watermark"]:
            invalidated = {a["ref"] for a in source["invalidated"]}
            if invalidated:
                with self.registry.transaction():
                    self.db.execute(
                        "UPDATE scan_alerts SET status='WITHDRAWN' WHERE job=? AND window=?",
                        (name, window),
                    )
                    self.registry._audit(
                        "SCAN_CORRECTION_WITHDRAWN", {"job": name, "window": window}
                    )
            return {"status": "ALREADY_PROCESSED", "corrected": bool(invalidated)}
        run_id = uuid.uuid4().hex
        body = {
            "data_ref": source["ref"],
            "request_digest": digest(request),
            "raw_input_digest": raw_input_digest,
            "registry_intake": registry_intake,
            "tests_charged": config["test_budget"],
            "owner_pid": os.getpid(),
            "lease_until": now + config["timeout"] + 10,
            "started_at": now,
        }
        with self.registry.transaction():
            current = self.db.execute(
                "SELECT * FROM scan_jobs WHERE name=?", (name,)
            ).fetchone()
            if not current["enabled"]:
                return {"status": "STOPPED"}
            if current["watermark"] is not None and window <= current["watermark"]:
                return {"status": "ALREADY_PROCESSED"}
            if self.db.execute(
                "SELECT 1 FROM scan_runs WHERE job=? AND status='RUNNING'", (name,)
            ).fetchone():
                return {"status": "BUSY"}
            spent = sum(
                json.loads(r[0])["tests_charged"]
                for r in self.db.execute(
                    "SELECT body FROM scan_runs WHERE job=?", (name,)
                )
            )
            spent += sum(
                json.loads(r[0]).get("tests_charged", 0)
                for r in self.db.execute(
                    "SELECT body FROM scan_confirmations WHERE job=?", (name,)
                )
            )
            if spent + config["test_budget"] > config["lifetime_test_budget"]:
                self.db.execute("UPDATE scan_jobs SET enabled=0 WHERE name=?", (name,))
                return {"status": "BUDGET_EXHAUSTED"}
            self.db.execute(
                "INSERT INTO scan_runs VALUES (?,?,?,?,?)",
                (run_id, name, window, "RUNNING", json.dumps(body)),
            )
            self.db.execute(
                "UPDATE scan_jobs SET next_due=? WHERE name=?",
                (now + config["interval_seconds"], name),
            )
        try:
            report = None
            skill_usage = None
            if config["skill_name"]:
                skills = SkillGovernance(self.registry.path)
                try:
                    skill_usage = skills.replay(
                        name=config["skill_name"],
                        context=config["skill_context"],
                        task_id="scan:" + name + ":" + str(window),
                        data_ref=source["ref"],
                        window=window,
                    )
                    candidate = skill_usage.get("report")
                    if candidate and candidate["operation"] == "scan_window":
                        report = candidate
                finally:
                    skills.close()
            if report is None:
                report = isolated_replay(
                    "scan_window",
                    request,
                    {
                        "task_id": "scan:" + name + ":" + str(window),
                        "data_ref": source["ref"],
                        "skill_ref": "registered_scan_default",
                    },
                    timeout=config["timeout"],
                )
            if (
                report["execution_status"] != "COMPLETED"
                or "scan" not in report["result"]
            ):
                raise ValueError("scan worker rejected request")
            result = report["result"]["scan"]
            if result["manifest"]["total_tests_spent"] > config["test_budget"]:
                raise ValueError("worker exceeded scan budget")
            evidence = self.registry.add_asset(
                "manifest", report, dependencies=[source["ref"]]
            )
            body.update(
                tests_charged=result["manifest"]["total_tests_spent"],
                result=result,
                evidence_ref=evidence,
                skill_usage=skill_usage,
                cost=report["cost"],
                completed_at=time.time(),
            )
            with self.registry.transaction():
                for alert in [*result["watchlist"], *result["deferred"]]:
                    alert_id = digest({"job": name, "alert_id": alert["alert_id"]})
                    self.db.execute(
                        "INSERT OR IGNORE INTO scan_alerts VALUES (?,?,?,?,?)",
                        (
                            alert_id,
                            name,
                            window,
                            "WATCHLIST",
                            json.dumps(
                                {
                                    **alert,
                                    "alert_id": alert_id,
                                    "evidence_ref": evidence,
                                }
                            ),
                        ),
                    )
                if (
                    self.db.execute(
                        "UPDATE scan_runs SET status='COMPLETED',body=? WHERE id=? AND status='RUNNING'",
                        (json.dumps(body), run_id),
                    ).rowcount
                    != 1
                ):
                    raise ValueError("scan lease lost")
                self.db.execute(
                    "UPDATE scan_jobs SET watermark=? WHERE name=?", (window, name)
                )
                self.registry._audit(
                    "SCAN_COMPLETED",
                    {
                        "job": name,
                        "window": window,
                        "run_id": run_id,
                        "evidence_ref": evidence,
                    },
                )
            return {"status": "COMPLETED", "run_id": run_id, **body}
        except Exception as exc:  # noqa: BLE001 -- durable job failure boundary
            body.update(error=str(exc), reason_codes=["DATA_INVALID"])
            with self.registry.transaction():
                self.db.execute(
                    "UPDATE scan_runs SET status='FAILED',body=? WHERE id=? AND status='RUNNING'",
                    (json.dumps(body), run_id),
                )
                self.registry._audit(
                    "SCAN_FAILED", {"run_id": run_id, "error": str(exc)}
                )
            return {"status": "FAILED", "run_id": run_id, **body}

    def _event(self, event, body):
        with self.registry.transaction():
            self.registry._audit(event, body)

    def alerts(self, name):
        result = []
        for row in self.db.execute(
            "SELECT * FROM scan_alerts WHERE job=? ORDER BY rowid", (name,)
        ):
            body = json.loads(row["body"])
            valid = self.registry.asset(body["evidence_ref"])["status"] == "VALID"
            result.append({**body, "status": row["status"] if valid else "WITHDRAWN"})
        return result

    def confirm(
        self,
        *,
        name,
        alert_ids,
        days,
        residual,
        factors,
        metric_series=None,
        bootstrap_reps=199,
        block_length=3,
    ):
        from .watchlist_scan import confirm_watchlist

        config = self.status(name)["config"]
        if config["error_policy"] == "exploratory_only":
            raise ValueError("job has no registered across-time confirmation policy")
        candidates = {a["alert_id"]: a for a in self.alerts(name)}
        if (
            not alert_ids
            or len(set(alert_ids)) != len(alert_ids)
            or any(
                a not in candidates or candidates[a]["status"] != "WATCHLIST"
                for a in alert_ids
            )
        ):
            raise ValueError("valid unconfirmed watchlist family required")
        selected = [candidates[a] for a in alert_ids]
        start, end = min(days), max(days)
        with self.registry.transaction():
            old = self.db.execute(
                "SELECT * FROM scan_confirmations WHERE job=?", (name,)
            ).fetchall()
            if any(
                max(start, r["window_start"]) <= min(end, r["window_end"]) for r in old
            ):
                raise ValueError("confirmation window already consumed")
            n = len(old) + 1
            alpha = config["total_alpha"] / (n * (n + 1))
            spent = sum(
                json.loads(r[0])["tests_charged"]
                for r in self.db.execute(
                    "SELECT body FROM scan_runs WHERE job=?", (name,)
                )
            ) + sum(json.loads(r["body"]).get("tests_charged", 0) for r in old)
            if spent + len(alert_ids) > config["lifetime_test_budget"]:
                raise ValueError("confirmation exceeds lifetime test budget")
            consumed = {
                "tests_charged": len(alert_ids),
                "status": "CONSUMED",
                "alert_ids": alert_ids,
                "alpha": alpha,
                "attempt": n,
            }
            self.db.execute(
                "INSERT INTO scan_confirmations VALUES (?,?,?,?)",
                (name, start, end, json.dumps(consumed)),
            )
            self.registry._audit(
                "SCAN_CONFIRMATION_CONSUMED",
                {"job": name, "window": [start, end], **consumed},
            )
        try:
            result = confirm_watchlist(
                selected,
                days,
                residual,
                factors,
                metric_series=metric_series,
                alpha=alpha,
                bootstrap_reps=bootstrap_reps,
                block_length=block_length,
            )
            result["tests_charged"] = len(alert_ids)
            result["error_policy"] = (
                "summable_alpha_spending_conditional_on_valid_null_pvalues"
            )
            with self.registry.transaction():
                self.db.execute(
                    "UPDATE scan_confirmations SET body=? WHERE job=? AND window_start=? AND window_end=?",
                    (json.dumps(result), name, start, end),
                )
                for r in result["results"]:
                    self.db.execute(
                        "UPDATE scan_alerts SET status=? WHERE id=?",
                        (
                            "FACTOR_CANDIDATE"
                            if r["confirmed"]
                            else "CONFIRMATION_INCONCLUSIVE",
                            r["alert_id"],
                        ),
                    )
                self.registry._audit(
                    "SCAN_CONFIRMATION_COMPLETED", {"job": name, "result": result}
                )
            return result
        except Exception as exc:
            self._event(
                "SCAN_CONFIRMATION_FAILED",
                {"job": name, "window": [start, end], "error": str(exc)},
            )
            raise
