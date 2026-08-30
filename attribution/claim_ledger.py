"""Claim Ledger v5: claim types, promotion gates, and the conclusion state machine."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CLAIM_TYPES = (
    "ASSOCIATION_ONLY",
    "FACTOR_CANDIDATE",
    "BUNDLE_EFFECT",
    "EXPLORATORY_HETEROGENEITY",
    "HETEROGENEOUS_TREATMENT_EFFECT",
    "MEDIATION_CANDIDATE",
    "COMPONENT_EFFECT",
    "EXPERIMENT_INCONCLUSIVE",
)

ALLOWED_VERBS = {
    "ASSOCIATION_ONLY": ["观察到", "同时出现", "对应"],
    "FACTOR_CANDIDATE": ["发现候选", "值得验证"],
    "BUNDLE_EFFECT": ["在本实验中提升", "在本实验中降低", "估计"],
    "EXPLORATORY_HETEROGENEITY": ["探索性提示", "未经独立确认"],
    "HETEROGENEOUS_TREATMENT_EFFECT": ["在该分群中放大", "在该分群中缓解"],
    "MEDIATION_CANDIDATE": ["可能通过", "路径候选"],
    "COMPONENT_EFFECT": ["独立随机化显示", "组件级效应"],
    "EXPERIMENT_INCONCLUSIVE": ["证据不足", "需要更多数据"],
}

PROHIBITED_VERBS = ["导致", "根因是", "证明"]

STATES = (
    "OBSERVED_ANOMALY",
    "FACTORS_DISCOVERED",
    "BUNDLE_EXPERIMENT_READY",
    "BUNDLE_EFFECT_ESTIMATED",
    "HETEROGENEITY_RANKED",
    "COMPONENT_EXPERIMENT_DESIGNED",
    "COMPONENT_EFFECT_ESTIMATED",
    "POSTERIOR_UPDATED",
    "DECISION_READY",
)

REFUSALS = (
    "ASSOCIATION_ONLY",
    "FACTOR_SPACE_INCOMPLETE",
    "EXPERIMENT_NOT_IDENTIFIED",
    "INCONCLUSIVE_NEED_MORE_DATA",
)


class ClaimLedger:
    def __init__(self) -> None:
        self.claims: list[dict[str, Any]] = []
        self.state: str = "OBSERVED_ANOMALY"
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"claim-{self._counter:03d}"

    def add_claim(
        self,
        claim_type: str,
        statement: str,
        estimand: str | None = None,
        evidence_refs: list[str] | None = None,
        posterior_probability: float | None = None,
        credible_interval: list[float] | None = None,
        practical_threshold: float | None = None,
        assumptions: list[str] | None = None,
        selected_after_seeing_outcome: bool = False,
    ) -> dict[str, Any]:
        if claim_type not in CLAIM_TYPES:
            raise ValueError(f"unknown claim_type: {claim_type}")
        if selected_after_seeing_outcome and claim_type in (
            "HETEROGENEOUS_TREATMENT_EFFECT", "COMPONENT_EFFECT",
        ):
            # Selection-bias guard: discovered and estimated on the same data.
            claim_type = "EXPLORATORY_HETEROGENEITY"
        claim = {
            "claim_id": self._next_id(),
            "claim_type": claim_type,
            "statement": statement,
            "estimand": estimand,
            "evidence_refs": evidence_refs or [],
            "posterior_probability": posterior_probability,
            "credible_interval": credible_interval,
            "practical_threshold": practical_threshold,
            "assumptions": assumptions or [],
            "allowed_verbs": ALLOWED_VERBS[claim_type],
            "prohibited_verbs": PROHIBITED_VERBS,
            "selected_after_seeing_outcome": selected_after_seeing_outcome,
        }
        self.claims.append(claim)
        return claim

    def can_promote_to_component_effect(self, design_record: Mapping[str, Any]) -> bool:
        """COMPONENT_EFFECT requires independent randomization of the factor."""
        return all([
            design_record.get("independent_randomization") is True,
            design_record.get("assignment_provenance") in {"experiment_platform", "signed_config"},
            design_record.get("design_code_traceable") is True,
            design_record.get("stable_randomization_unit") is True,
        ])

    def transition(self, target: str) -> str:
        if target not in STATES:
            raise ValueError(f"unknown state: {target}")
        if STATES.index(target) < STATES.index(self.state):
            raise ValueError(f"cannot move backwards: {self.state} -> {target}")
        self.state = target
        return self.state

    def render(self) -> dict[str, Any]:
        return {"state": self.state, "claims": self.claims}
