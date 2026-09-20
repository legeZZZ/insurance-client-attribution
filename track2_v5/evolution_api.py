"""Public JSON backend operations for governed evolution, feedback and resident scanning."""

from __future__ import annotations

from .experience_store import GovernedPriorStore
from .feedback_service import FeedbackService
from .scan_service import ScanService
from .skill_governance import SkillGovernance


def _execute(service, action, parameters, allowed):
    try:
        if action not in allowed:
            raise ValueError("unknown governed backend operation")
        return getattr(service, action)(**parameters)
    finally:
        service.close()


def execute_skills(*, db_path, action, parameters=None, skill_store_path=None):
    return _execute(
        SkillGovernance(db_path, skill_store_path=skill_store_path),
        action,
        parameters or {},
        {
            "learn_from_feedback",
            "export_markdown",
            "capture",
            "trace",
            "propose",
            "get",
            "review",
            "freeze_suite",
            "validate",
            "approve",
            "publish",
            "retrieve",
            "replay",
            "monitor",
            "suspend_scope",
            "rollback",
        },
    )


def execute_feedback(*, db_path, action, parameters=None):
    result = _execute(
        FeedbackService(db_path),
        action,
        parameters or {},
        {"submit", "read", "queue", "register_supplement", "calibration", "ledger"},
    )
    return result if isinstance(result, dict) else {"result": result}


def execute_scan(*, db_path, action, parameters=None):
    result = _execute(
        ScanService(db_path),
        action,
        parameters or {},
        {
            "configure",
            "start",
            "stop",
            "status",
            "tick",
            "recover",
            "alerts",
            "confirm",
            "launch",
        },
    )
    return result if isinstance(result, dict) else {"result": result}


def execute_prior(*, db_path, action, parameters=None):
    return _execute(
        GovernedPriorStore(db_path),
        action,
        parameters or {},
        {"observe", "prior_for", "estimate_rate"},
    )
