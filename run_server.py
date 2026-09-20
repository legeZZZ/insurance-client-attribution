#!/usr/bin/env python3
"""attribution console server."""

from __future__ import annotations

import argparse
import json
import math
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "src"))

from goai_control_tower.configuration import load_config
from goai_control_tower.track2 import (
    case_experiment_metadata,
    default_metric_contract,
    generate_dataset,
    public_case,
    run_case,
)
from goai_control_tower.track2_analysis import sanitize_rows
from goai_control_tower.track2_benchmark import run_hidden_benchmark
from goai_control_tower.track2_datasets import load_dataset_catalog
from goai_control_tower.track2_real_data import run_real_data_case
from goai_control_tower.track2_v5_bridge import (
    evaluate_with_bayes,
    run_line_b_monthly_review,
)
from track2_v5.agent_chat import handle_message, reset_session
from track2_v5.scenario_reports import (
    SCENARIOS,
    render_markdown,
    run_scenario,
    set_company_config,
)
import console_v2

RUNTIME = PROJECT / "runtime_data"
STATIC = PROJECT / "web" / "static"
MAX_REQUEST_BODY = 64 * 1024
VALID_CASES = {"A", "B", "C"}
AUTH_TOKEN = os.environ.get("T2_AUTH_TOKEN", "").strip()
COMPANY_LABEL: str | None = None


def audit(event: str, **fields: object) -> None:
    """Append one JSON line to the audit log (intranet compliance trail)."""
    try:
        from datetime import datetime

        RUNTIME.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "event": event,
            **fields,
        }
        with (RUNTIME / "audit.log").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def bounded_int(value: str, *, minimum: int, maximum: int, name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def bounded_float(value: str, *, minimum: float, maximum: float, name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def valid_case(value: str) -> str:
    case = value.upper()
    if case not in VALID_CASES:
        raise ValueError(f"case must be one of {', '.join(sorted(VALID_CASES))}")
    return case


class Handler(BaseHTTPRequestHandler):
    server_version = "AttributionConsole/0.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def authorized(self) -> bool:
        """If T2_AUTH_TOKEN is set, require `Authorization: Bearer <token>` for /api/*."""
        if not AUTH_TOKEN:
            return True
        header = self.headers.get("Authorization", "")
        if header == f"Bearer {AUTH_TOKEN}":
            return True
        audit("auth_rejected", path=self.path, client=self.client_address[0])
        self.send_json({"error": "unauthorized"}, status=401)
        return False

    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path: str) -> None:
        relative = "final-console-v3.html" if path == "/" else path.lstrip("/")
        candidate = (STATIC / relative).resolve()
        if STATIC.resolve() not in candidate.parents and candidate != STATIC.resolve():
            self.send_error(404)
            return
        if not candidate.is_file():
            self.send_error(404)
            return
        body = candidate.read_bytes()
        content_type = (
            mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        )
        self.send_response(200)
        self.send_header(
            "Content-Type",
            content_type
            + (
                "; charset=utf-8"
                if content_type.startswith("text/")
                or content_type == "application/javascript"
                else ""
            ),
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_download(self, text: str, filename: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path.startswith("/api/") and not self.authorized():
            return
        if parsed.path == "/api/health":
            self.send_json(
                {
                    "status": "ok",
                    "runtime": "local-attribution-conformance",
                    "version": "0.1.0",
                    "company_data": COMPANY_LABEL is not None,
                    "auth": bool(AUTH_TOKEN),
                }
            )
            return
        if parsed.path.startswith("/api/v2/"):
            v2_get = {
                "/api/v2/overview": console_v2.overview,
                "/api/v2/factors": console_v2.factors,
                "/api/v2/watchlist": console_v2.watchlist,
                "/api/v2/feedback/queue": console_v2.feedback_queue,
                "/api/v2/skills": console_v2.list_skills,
                "/api/v2/conflicts": console_v2.conflicts,
                "/api/v2/evidence": console_v2.evidence,
                "/api/v2/alerts": console_v2.alerts,
                "/api/v2/factors/ledger": console_v2.factor_ledger,
            }
            handler = v2_get.get(parsed.path)
            if handler is None:
                self.send_json({"error": "unknown v2 endpoint"}, status=404)
                return
            try:
                self.send_json(handler(RUNTIME / "console_v2"))
            except Exception as exc:  # noqa: BLE001 - keep failures machine-readable
                self.send_json({"error": "v2 endpoint failed", "detail": str(exc)},
                               status=500)
            return
        if parsed.path == "/api/track2/case":
            try:
                case = valid_case(query.get("case", ["A"])[0])
            except ValueError as exc:
                self.send_json({"error": str(exc)}, status=400)
                return
            self.send_json(public_case(run_case(RUNTIME, case)))
            return
        if parsed.path == "/api/track2/benchmark":
            try:
                seed_count = bounded_int(
                    query.get("seeds", ["8"])[0],
                    minimum=1,
                    maximum=20,
                    name="seeds",
                )
            except ValueError as exc:
                self.send_json({"error": str(exc)}, status=400)
                return
            seeds = tuple(100 + index * 101 for index in range(seed_count))
            self.send_json(run_hidden_benchmark(seeds=seeds))
            return
        if parsed.path == "/api/track2/datasets":
            self.send_json(load_dataset_catalog())
            return
        if parsed.path == "/api/track2/real-data":
            csv_path = RUNTIME / "datasets" / "uci-bank-marketing" / "data.csv"
            if not csv_path.is_file():
                self.send_json(
                    {
                        "error": "真实数据尚未下载",
                        "dataset": "UCI Bank Marketing",
                        "download_command": "python3 -m runtime --fetch-real-data",
                    },
                    status=404,
                )
                return
            self.send_json(run_real_data_case(RUNTIME, csv_path))
            return
        if parsed.path == "/api/track2/bayes-case":
            # v3 gate + v5 Bayesian decision layer (refuses when the gate fails).
            try:
                case = valid_case(query.get("case", ["C"])[0])
                threshold = bounded_float(
                    query.get("threshold", ["0.01"])[0],
                    minimum=0.0,
                    maximum=1.0,
                    name="threshold",
                )
            except ValueError as exc:
                self.send_json({"error": str(exc)}, status=400)
                return
            rows, _truth = generate_dataset(case, seed=42, n=1200)
            bundle = {
                "rows": sanitize_rows(rows),
                "metric_contract": default_metric_contract(),
                "experiment_metadata": case_experiment_metadata(case),
            }
            self.send_json(
                evaluate_with_bayes(
                    bundle, practical_threshold=threshold, hte_segment_field="channel"
                )
            )
            return
        if parsed.path == "/api/track2/line-b-review":
            self.send_json(run_line_b_monthly_review(RUNTIME))
            return
        if parsed.path == "/api/track2/scenarios":
            self.send_json({"scenarios": SCENARIOS})
            return
        if parsed.path == "/api/track2/scenario-run":
            scenario = query.get("scenario", ["line_a"])[0]
            audit("scenario_run", scenario=scenario, client=self.client_address[0])
            try:
                self.send_json(run_scenario(scenario, RUNTIME))
            except KeyError as exc:
                self.send_json(
                    {"error": str(exc), "known": [s["id"] for s in SCENARIOS]},
                    status=404,
                )
            except Exception as exc:  # noqa: BLE001 - keep pipeline failures machine-readable
                self.send_json(
                    {
                        "error": "scenario execution failed",
                        "scenario": scenario,
                        "detail": str(exc),
                    },
                    status=500,
                )
            return
        if parsed.path == "/api/track2/scenario-report":
            scenario = query.get("scenario", ["line_a"])[0]
            try:
                report = run_scenario(scenario, RUNTIME)
            except KeyError as exc:
                self.send_json({"error": str(exc)}, status=404)
                return
            except Exception as exc:  # noqa: BLE001 - report failures share the JSON contract
                self.send_json(
                    {
                        "error": "scenario report failed",
                        "scenario": scenario,
                        "detail": str(exc),
                    },
                    status=500,
                )
                return
            self.send_download(
                render_markdown(report), f"attribution_report_{scenario}.md"
            )
            return
        self.serve_static(parsed.path)

    def read_json_body(self):
        raw_length = self.headers.get("Content-Length", "0")
        length = bounded_int(
            raw_length, minimum=1, maximum=MAX_REQUEST_BODY, name="Content-Length"
        )
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("invalid JSON body") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/") and not self.authorized():
            return
        if parsed.path.startswith("/api/v2/"):
            try:
                payload = self.read_json_body()
            except ValueError as exc:
                self.send_json({"error": str(exc)}, status=400)
                return
            v2_post = {
                "/api/v2/feedback": console_v2.submit_feedback,
                "/api/v2/skills/action": console_v2.skill_action,
                "/api/v2/conflicts/input": console_v2.conflict_input,
                "/api/v2/alerts/action": console_v2.alert_action,
                "/api/v2/factors/manage": console_v2.factor_manage,
            }
            handler = v2_post.get(parsed.path)
            if handler is None:
                self.send_json({"error": "unknown v2 endpoint"}, status=404)
                return
            try:
                result = handler(RUNTIME / "console_v2", payload)
            except (ValueError, KeyError) as exc:
                self.send_json({"error": str(exc), "governance": True}, status=400)
                return
            except Exception as exc:  # noqa: BLE001
                self.send_json({"error": "v2 action failed", "detail": str(exc)},
                               status=500)
                return
            audit("v2_action", endpoint=parsed.path,
                  client=self.client_address[0])
            self.send_json(result)
            return
        if parsed.path == "/api/track2/chat":
            try:
                payload = self.read_json_body()
            except ValueError as exc:
                self.send_json({"error": str(exc)}, status=400)
                return
            session_id = str(payload.get("session_id") or "default")
            message = str(payload.get("message") or "")
            if not message.strip():
                self.send_json({"error": "message is required"}, status=400)
                return
            if message.strip().lower() in {"reset", "重置"}:
                reset_session(session_id)
                self.send_json({"reply": "会话已重置。", "stage": "intent"})
                return
            self.send_json(handle_message(session_id, message, RUNTIME))
            return
        self.send_error(404)


def _auto_seed_console(runtime: Path) -> None:
    """Seed the v2 console workspace on first boot.

    Hosts with ephemeral filesystems (e.g. Render) wipe runtime_data on every
    deploy, so the demo workspace must be rebuilt at startup. Seeding runs the
    real track2_v5 pipeline and only needs numpy; failures are non-fatal —
    the console page then falls back to its bundled replay data.
    """
    if (runtime / "console_v2" / "watchlist.json").is_file():
        return
    import subprocess

    try:
        subprocess.run(
            [sys.executable, str(PROJECT / "tools" / "seed_console_v2.py")],
            check=True,
            timeout=300,
        )
        print("console_v2 workspace auto-seeded", flush=True)
    except Exception as exc:  # noqa: BLE001 - best-effort seed, never block boot
        print(f"console_v2 auto-seed skipped: {exc}", flush=True)


def main() -> None:
    global COMPANY_LABEL, RUNTIME
    parser = argparse.ArgumentParser(description="Run the GOAI attribution console")
    parser.add_argument("port", nargs="?", type=int, help="port override")
    parser.add_argument("--config", type=Path, help="JSON configuration file")
    parser.add_argument(
        "--data-config",
        type=Path,
        help="company data source config (see config.example.json); enables company_line_b",
    )
    parser.add_argument("--host", help="host override")
    parser.add_argument("--runtime", help="runtime output directory override")
    args = parser.parse_args()
    config = load_config(args.config)
    RUNTIME = Path(args.runtime or config["runtime"]["output_dir"]).expanduser()
    _auto_seed_console(RUNTIME)
    if args.data_config:
        from track2_v5.adapters import load_config as load_data_config

        data_config = load_data_config(args.data_config)
        set_company_config(data_config)
        COMPANY_LABEL = data_config.label
        print(
            f"company data source: {data_config.label} ({data_config.data_dir})",
            flush=True,
        )
    host = args.host or os.environ.get("HOST") or config["server"]["host"]
    port = (
        args.port
        if args.port is not None
        else int(os.environ.get("PORT") or config["server"]["port"])
    )
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"GOAI attribution Console: http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
