"""Same data and fixed search ceilings; measures selection, overlap and cost."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from track2_v5.rate_aware_rca import discover_rate_candidates, make_demo_panel
from track2_v5.risk_loc import discover_risk_candidates


def compare(seeds=20):
    records = []
    for seed in range(seeds):
        fixture = make_demo_panel(seed=seed)
        for name, algorithm in (
            ("beam", discover_rate_candidates),
            ("riskloc", discover_risk_candidates),
        ):
            result = algorithm(
                fixture["panel"],
                ("region", "channel", "version"),
                (0, 39),
                (40, 59),
                max_candidates=1000,
                top_k=8,
                max_seconds=2.0,
            )
            scopes = [c["scope"] for c in result["candidates"]]
            atoms = {tuple(sorted(r["scope"].items())) for r in fixture["panel"]}
            cover = [
                sum(
                    all(dict(a).get(k) == v for k, v in scope.items())
                    for scope in scopes
                )
                for a in atoms
            ]
            records.append(
                {
                    "seed": seed,
                    "algorithm": name,
                    "recall_at_8": int(fixture["truth"]["affected_scope"] in scopes),
                    "overlap_redundancy": sum(max(0, n - 1) for n in cover)
                    / max(1, sum(cover)),
                    "evaluations": result["search_manifest"]["evaluated_candidates"],
                    "seconds": result["runtime_seconds"],
                    "budget_exhausted": result["search_manifest"]["budget_exhausted"],
                }
            )
    summaries = {}
    for name in ("beam", "riskloc"):
        group = [r for r in records if r["algorithm"] == name]
        summaries[name] = {
            key: sum(r[key] for r in group) / len(group)
            for key in ("recall_at_8", "overlap_redundancy", "evaluations", "seconds")
        }
    return {
        "scope": "fixed_single_local_rate_drop_fixture_only",
        "search_budget": {"evaluations": 1000, "seconds": 2.0, "top_k": 8},
        "summaries": summaries,
        "runs": records,
        "limitations": [
            "does_not_measure_mixed_sign_or_multiple_root_causes",
            "search_deadline_excludes_result_assembly",
            "no_causal_claim",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    args = parser.parse_args()
    if args.seeds <= 0:
        parser.error("seeds must be positive")
    print(json.dumps(compare(args.seeds), indent=2))
