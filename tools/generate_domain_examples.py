"""Reproducible, replaceable insurance/ecommerce manifests for one shared engine."""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from track2_v5.persistence import atomic_json


def generate(output):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    for domain, label, factor in [
        ("insurance", "policy_conversion", "contact_intensity"),
        ("ecommerce", "checkout_conversion", "promotion_intensity"),
    ]:
        folder = root / domain
        folder.mkdir(exist_ok=True)
        rng = np.random.default_rng(90210)
        x = rng.normal(size=100)
        y = 0.02 * np.roll(x, 2) + rng.normal(size=100) * 0.002
        metric = {
            "name": label,
            "numerator": "converted",
            "denominator": "eligible_users",
            "aggregation": "ratio_of_sums",
            "unit": "rate",
            "analysis_unit": "user",
            "target_population": "eligible_users",
            "timezone": "UTC",
            "window": [0, 99],
            "maturity_days": 2,
            "deduplication": "unit_id",
        }
        source = {
            "source_uri": f"company://{domain}/sandbox",
            "license_ref": "declared-company-authorized",
            "timezone": "UTC",
            "available_day": 101,
        }
        rows = [
            {"subject_key": f"u{i}", "assigned_arm": int(i % 2), "conversion": int(v)}
            for i, v in enumerate(rng.binomial(1, 0.2 + 0.08 * (np.arange(600) % 2)))
        ]
        atomic_json(folder / "observations.json", rows)
        panel = [
            {
                "day": i,
                "control": 0.2,
                "treated": float(0.2 + y[i]),
                "residual": float(y[i]),
            }
            for i in range(100)
        ]
        factors = [
            {
                "factor_id": factor,
                "day": i,
                "value": float(x[i]),
                "effect_shape": "persistent",
                "unit": "index",
            }
            for i in range(100)
        ]
        atomic_json(folder / "panel.json", panel)
        atomic_json(folder / "factors.json", factors)
        for line in ["A", "B", "C"]:
            body = {
                "schema": "enterprise/1",
                "case_id": domain + "-" + line,
                "domain": domain,
                "line": line,
                "source": source,
                "metric_contract": metric,
            }
            if line == "A":
                body["tables"] = {
                    "observations": {
                        "path": "observations.json",
                        "field_mapping": {
                            "subject_key": "unit_id",
                            "assigned_arm": "treatment",
                            "conversion": "outcome",
                        },
                    }
                }
                body["parameters"] = {
                    "assignment_ref": "declared:sandbox-randomized",
                    "randomized": True,
                    "no_interference_ref": "declared:independent-units",
                }
            else:
                body["tables"] = {
                    "panel": {"path": "panel.json"},
                    "factors": {"path": "factors.json"},
                }
                body["parameters"] = {"lags": [2], "budget": 3, "test_budget": 30}
            path = folder / (line + ".json")
            atomic_json(path, body)
            paths.append(str(path.resolve()))
    return paths


if __name__ == "__main__":
    print(
        json.dumps(
            generate(sys.argv[1] if len(sys.argv) > 1 else "examples/domains"),
            ensure_ascii=False,
            indent=2,
        )
    )
