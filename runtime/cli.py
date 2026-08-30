"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .benchmark import run_benchmark
from .cases import public_case, run_case
from .configuration import load_config, resolve_output_dir, validate_evidence_pack
from .dataset_catalog import load_dataset_catalog
from .real_data import fetch_bank_marketing_csv, run_real_data_case


def _read_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the causal-readiness cases")
    parser.add_argument("--config", type=Path, help="JSON configuration file")
    parser.add_argument("--output", help="runtime output directory")
    parser.add_argument("--benchmark", action="store_true", help="Run the process-isolated hidden benchmark")
    parser.add_argument("--benchmark-seeds", type=int, default=8, help="Number of deterministic hidden benchmark seeds")
    parser.add_argument("--datasets", action="store_true", help="Print the verified public dataset catalog")
    parser.add_argument("--real-data", action="store_true", help="Analyze the cached UCI Bank Marketing history")
    parser.add_argument("--fetch-real-data", action="store_true", help="Download, verify and analyze UCI Bank Marketing")
    parser.add_argument("--real-data-path", type=Path, help="Override the UCI Bank Marketing CSV path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    output_dir = resolve_output_dir(config, args.output)
    result: dict[str, Any] = {}

    result["cases"] = {}
    for case in config["runtime"].get("cases", ["A", "B", "C"]):
        public = public_case(run_case(output_dir, case))
        validate_evidence_pack(public, config)
        result["cases"][case] = {
            "state": public["summary"]["final_state"],
            "causal_outcome": public["summary"]["causal_outcome"],
            "claim_type": public["summary"]["claim_type"],
            "evidence_pack": public.get("evidence_pack_path"),
        }
    if args.benchmark:
        seeds = tuple(100 + index * 101 for index in range(max(1, args.benchmark_seeds)))
        result["cases"]["benchmark"] = run_benchmark(seeds=seeds)

    if args.datasets:
        result["dataset_catalog"] = load_dataset_catalog()

    if args.real_data or args.fetch_real_data:
        real_data_path = args.real_data_path or output_dir / "datasets" / "uci-bank-marketing" / "data.csv"
        if args.fetch_real_data:
            fetch_bank_marketing_csv(real_data_path)
        result["real_data"] = run_real_data_case(output_dir, real_data_path)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
