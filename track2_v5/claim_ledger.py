"""Claim Ledger v5: claim types, promotion gates, and the conclusion state machine."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .publication import DISPLAY_TYPES, STRONG_LEGACY, govern_output, publish_conclusion

CLAIM_TYPES = (
    "WATCHLIST",
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
    # D7: one level below FACTOR_CANDIDATE — worth watching, not a candidate.
    "WATCHLIST": ["值得盯防", "持续观察"],
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
        self._jumps: list[dict[str, Any]] = []

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
        design_record: Mapping[str, Any] | None = None,
        contracts: dict | None = None,
    ) -> dict[str, Any]:
        if claim_type not in (*CLAIM_TYPES, *DISPLAY_TYPES):
            raise ValueError(f"unknown claim_type: {claim_type}")
        if selected_after_seeing_outcome and claim_type in (
            "HETEROGENEOUS_TREATMENT_EFFECT",
            "COMPONENT_EFFECT",
        ):
            # Selection-bias guard: discovered and estimated on the same data.
            claim_type = "EXPLORATORY_HETEROGENEITY"
            # rev5 P1-F4: do not keep a statement written for the stronger
            # claim type after downgrading; mark the downgrade explicitly.
            statement = "[已降级：发现与估计使用同一数据] " + statement
        if claim_type == "COMPONENT_EFFECT":
            # rev5 P1-F4: the ledger enforces the promotion gate itself; a
            # caller may not write COMPONENT_EFFECT by passing checks outside
            # the ledger (the old API allowed direct writes).
            if design_record is None or not self.can_promote_to_component_effect(
                design_record
            ):
                raise ValueError(
                    "COMPONENT_EFFECT requires a design_record passing "
                    "can_promote_to_component_effect (independent randomization, "
                    "traceable provenance and stable randomization unit)"
                )
        publication = None
        if contracts is not None:
            if (
                selected_after_seeing_outcome
                and contracts["EffectEstimate"]["selection_status"] != "exploratory"
            ):
                raise ValueError(
                    "outcome-selected claim requires exploratory effect contract"
                )
            publication = publish_conclusion(
                contracts,
                practical_threshold=practical_threshold or 0,
                component_design=dict(design_record)
                if claim_type in {"COMPONENT_EFFECT", "COMPONENT_RANDOMIZED_EFFECT"}
                and design_record
                else None,
            )
            claim_type, statement = publication["claim_type"], publication["statement"]
            credible_interval = publication["statistical_uncertainty"]["interval"]
            posterior_probability = None
        elif claim_type in STRONG_LEGACY:
            claim_type = "ASSOCIATION_ONLY"
            statement = "原结论缺少统一识别和效应契约，作为待验证关联保留。"
            posterior_probability, credible_interval = None, None
        if selected_after_seeing_outcome:
            statement = "探索性分群候选，尚需独立确认。"
            posterior_probability, credible_interval = None, None
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
            "allowed_verbs": ALLOWED_VERBS.get(claim_type, ["估计", "观察到"]),
            "prohibited_verbs": PROHIBITED_VERBS,
            "selected_after_seeing_outcome": selected_after_seeing_outcome,
        }
        if publication is not None:
            claim["publication"] = publication
            claim["contracts"] = contracts
        self.claims.append(claim)
        return claim

    def can_promote_to_component_effect(self, design_record: Mapping[str, Any]) -> bool:
        """COMPONENT_EFFECT requires independent randomization of the factor."""
        return all(
            [
                design_record.get("independent_randomization") is True,
                design_record.get("assignment_provenance")
                in {"experiment_platform", "signed_config"},
                design_record.get("design_code_traceable") is True,
                design_record.get("stable_randomization_unit") is True,
            ]
        )

    def transition(self, target: str, skip_reason: str | None = None) -> str:
        if target not in STATES:
            raise ValueError(f"unknown state: {target}")
        current_index = STATES.index(self.state)
        target_index = STATES.index(target)
        if target_index < current_index:
            raise ValueError(f"cannot move backwards: {self.state} -> {target}")
        if target_index > current_index + 1 and not skip_reason:
            # rev5 P1-F4: forward jumps over intermediate states must be
            # explicit and auditable instead of silent.
            raise ValueError(
                f"skipping states requires skip_reason: {self.state} -> {target}"
            )
        if target_index > current_index + 1:
            self._jumps.append(
                {"from": self.state, "to": target, "skip_reason": skip_reason}
            )
        self.state = target
        return self.state

    def render(self) -> dict[str, Any]:
        return govern_output(
            {"state": self.state, "claims": self.claims, "state_jumps": self._jumps}
        )
