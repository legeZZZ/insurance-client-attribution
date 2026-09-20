"""Bounded local chat-completion policy transport. Model output is only a proposal."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from .loop_controller import validate_proposal


def rule_proposal(snapshot, factor_ids):
    if snapshot["phase"] != "DISCOVERY" or snapshot["round"] or not factor_ids:
        return {
            "action": "STOP",
            "parameters": {},
            "rationale": "确定性规则：冻结候选并完成留出确认",
        }
    return {
        "action": "ADD_HYPOTHESES",
        "parameters": {"factor_ids": list(factor_ids)},
        "rationale": "确定性规则：检查登记的可用候选",
    }


class LocalPolicyAdapter:
    def __init__(self, endpoint=None, *, model="local", timeout=10, max_bytes=65536):
        if endpoint and (
            urlparse(endpoint).scheme not in {"http", "https"}
            or urlparse(endpoint).hostname not in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("local policy endpoint must use a loopback host")
        if not 0 < timeout <= 60 or not 1 <= max_bytes <= 1048576:
            raise ValueError("bounded timeout and response size required")
        self.endpoint, self.model, self.timeout, self.max_bytes = (
            endpoint,
            model,
            timeout,
            max_bytes,
        )

    def propose(self, snapshot, *, factor_ids):
        fallback = validate_proposal(rule_proposal(snapshot, factor_ids))
        start = time.monotonic()
        if not self.endpoint:
            return {
                "proposal": fallback,
                "provider": "rules",
                "fallback_reason": None,
                "elapsed_seconds": 0,
                "token_usage": {"total_tokens": 0},
            }
        try:
            body = json.dumps(
                {
                    "model": self.model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "system",
                            "content": "Return one JSON object with action, parameters, rationale. Actions: ADD_HYPOTHESES(factor_ids), SYNTHESIZE_FACTOR(disabled), ADJUST_THRESHOLD(min_abs_correlation), CHANGE_CONDITION_SET(factor_ids), QUANTIFY(request_id), STOP(reason_code optional). Never write evidence, state, alpha, windows or budgets. The deterministic controller evaluates every proposal.",
                        },
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "snapshot": snapshot,
                                    "available_factor_ids": factor_ids,
                                },
                                ensure_ascii=False,
                            ),
                        },
                    ],
                }
            ).encode()
            process = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(Path(__file__).with_name("policy_http_transport.py")),
                ],
                input=json.dumps(
                    {
                        "endpoint": self.endpoint,
                        "body": body.decode(),
                        "timeout": self.timeout,
                        "max_bytes": self.max_bytes,
                    }
                ).encode(),
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
            if process.returncode:
                raise ValueError(
                    "local transport failed: " + process.stderr.decode()[:100]
                )
            raw = process.stdout
            if len(raw) > self.max_bytes:
                raise ValueError("response exceeds policy budget")
            response = json.loads(raw)
            content = response["choices"][0]["message"]["content"]
            proposal = validate_proposal(json.loads(content))
            if proposal["action"] not in snapshot["allowed_actions"]:
                raise ValueError("action unavailable in current policy")
            if set(proposal["parameters"].get("factor_ids", [])) - set(factor_ids):
                raise ValueError("proposal references unavailable factors")
            return {
                "proposal": proposal,
                "provider": "local_http",
                "token_usage": response.get("usage"),
                "input_bytes": len(body),
                "output_bytes": len(raw),
                "fallback_reason": None,
                "elapsed_seconds": time.monotonic() - start,
            }
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            IndexError,
            subprocess.TimeoutExpired,
        ) as exc:
            return {
                "proposal": fallback,
                "provider": "rules",
                "fallback_reason": type(exc).__name__,
                "token_usage": None,
                "elapsed_seconds": time.monotonic() - start,
            }


def run_loop(controller, adapter=None):
    adapter = adapter or LocalPolicyAdapter()
    state = controller.recover()
    if state["phase"] != "DISCOVERY":
        return state
    body = controller.registry.asset(state["data_ref"])["body"]
    factor_ids = [f["factor_id"] for f in body["factor_series"]]
    while controller.state()["phase"] == "DISCOVERY":
        choice = adapter.propose(
            controller.snapshot_for_policy(), factor_ids=factor_ids
        )
        with controller.registry.transaction():
            controller.registry._audit(
                "POLICY_PROPOSED", {"loop": controller.loop_id, **choice}
            )
        try:
            controller.step(choice["proposal"])
        except ValueError:
            # Invalid model proposal is charged no statistical attempt, and cannot
            # buy another model round. Finish with the frozen valid candidates.
            if controller.state()["phase"] == "DISCOVERY":
                controller.finish("DATA_INVALID")
            else:
                raise
    return controller.state()
