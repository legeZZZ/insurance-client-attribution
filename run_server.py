#!/usr/bin/env python3
"""attribution console server."""

from __future__ import annotations

import argparse
import json
import math
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))

from attribution.agent_chat import handle_message, reset_session
from attribution.scenario_reports import SCENARIOS, render_markdown, run_scenario
from runtime.analysis import sanitize_rows
from runtime.bayes_bridge import (
    evaluate_with_bayes,
    run_line_b_monthly_review,
)
from runtime.benchmark import run_hidden_benchmark
from runtime.cases import (
    case_experiment_metadata,
    default_metric_contract,
    generate_dataset,
    public_case,
    run_case,
)
from runtime.configuration import load_config
from runtime.dataset_catalog import load_dataset_catalog
from runtime.real_data import run_real_data_case

RUNTIME = PROJECT / "runtime_data"
STATIC = PROJECT / "web" / "static"
MAX_REQUEST_BODY = 64 * 1024
VALID_CASES = {"A", "B", "C"}


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

    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path: str) -> None:
        relative = "semifinal-demo.html" if path == "/" else path.lstrip("/")
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
        if parsed.path == "/api/health":
            self.send_json(
                {
                    "status": "ok",
                    "runtime": "local-attribution-conformance",
                    "version": "0.1.0",
                }
            )
            return
        if parsed.path == "/api/attribution/case":
            try:
                case = valid_case(query.get("case", ["A"])[0])
            except ValueError as exc:
                self.send_json({"error": str(exc)}, status=400)
                return
            self.send_json(public_case(run_case(RUNTIME, case)))
            return
        if parsed.path == "/api/attribution/benchmark":
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
        if parsed.path == "/api/attribution/datasets":
            self.send_json(load_dataset_catalog())
            return
        if parsed.path == "/api/attribution/real-data":
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
        if parsed.path == "/api/attribution/bayes-case":
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
        if parsed.path == "/api/attribution/line-b-review":
            self.send_json(run_line_b_monthly_review(RUNTIME))
            return
        if parsed.path == "/api/attribution/scenarios":
            self.send_json({"scenarios": SCENARIOS})
            return
        if parsed.path == "/api/attribution/scenario-run":
            scenario = query.get("scenario", ["line_a"])[0]
            try:
                self.send_json(run_scenario(scenario, RUNTIME))
            except KeyError as exc:
                self.send_json(
                    {"error": str(exc), "known": [s["id"] for s in SCENARIOS]},
                    status=404,
                )
            return
        if parsed.path == "/api/attribution/scenario-report":
            scenario = query.get("scenario", ["line_a"])[0]
            try:
                report = run_scenario(scenario, RUNTIME)
            except KeyError as exc:
                self.send_json({"error": str(exc)}, status=404)
                return
            self.send_download(
                render_markdown(report), f"attribution_report_{scenario}.md"
            )
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/attribution/chat":
            raw_length = self.headers.get("Content-Length", "0")
            try:
                length = bounded_int(
                    raw_length,
                    minimum=1,
                    maximum=MAX_REQUEST_BODY,
                    name="Content-Length",
                )
            except ValueError as exc:
                status = (
                    413
                    if raw_length.isdigit() and int(raw_length) > MAX_REQUEST_BODY
                    else 400
                )
                self.send_json({"error": str(exc)}, status=status)
                return
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                self.send_json({"error": "invalid JSON body"}, status=400)
                return
            if not isinstance(payload, dict):
                self.send_json({"error": "JSON body must be an object"}, status=400)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the GOAI attribution console")
    parser.add_argument("port", nargs="?", type=int, help="port override")
    parser.add_argument("--config", type=Path, help="JSON configuration file")
    parser.add_argument("--host", help="host override")
    parser.add_argument("--runtime", help="runtime output directory override")
    args = parser.parse_args()
    config = load_config(args.config)
    global RUNTIME
    RUNTIME = Path(args.runtime or config["runtime"]["output_dir"]).expanduser()
    host = args.host or config["server"]["host"]
    port = args.port if args.port is not None else int(config["server"]["port"])
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
