"""Resolve and validate the exact Module 13 execution candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.planning_common import build

from src.execution.config import ExecutionSettings
from src.execution.errors import ExecutionValidationError
from src.ledger.config import load_comfort_ledger_settings
from src.ledger.evaluation import evaluate_candidates, rank_evaluations
from src.microtwin.config import load_microtwin_settings
from src.microtwin.rollout import rollout
from src.safety.config import load_safety_settings
from src.safety.guard import SafetyGuard
from src.safety.memory import SafetyMemory
from src.safety.models import ProposedCommand
from src.thermal_bank.config import load_thermal_bank_settings


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_execution_binding(
    settings: ExecutionSettings, plan_id: str | None = None
) -> dict[str, Any]:
    context, plans = build()
    micro = load_microtwin_settings(settings.root / "config/microtwin.yaml")
    rollouts = tuple(rollout(context, plan, micro) for plan in plans if plan.eligible)
    ledger = load_comfort_ledger_settings(settings.root / "config/comfort_ledger.yaml")
    bank = load_thermal_bank_settings(settings.root / "config/thermal_bank.yaml")
    evaluations = evaluate_candidates(context, plans, rollouts, ledger, bank)
    ranking = rank_evaluations(context, plans, rollouts, evaluations)
    selected = plan_id or ranking.selected_plan_id
    try:
        plan = next(item for item in plans if item.plan_id == selected)
        selected_rollout = next(item for item in rollouts if item.plan_id == selected)
        evaluation = next(item for item in evaluations if item.plan_id == selected)
    except StopIteration as exc:
        raise ExecutionValidationError("unknown_plan") from exc
    safety = load_safety_settings(settings.root / "config/safety_guard.yaml")
    if not plan.eligible or not evaluation.eligible:
        raise ExecutionValidationError("plan_no_longer_eligible")
    if evaluation.debt_status == "BLOCKING":
        raise ExecutionValidationError("blocking_debt")
    if selected_rollout.qualification_status == "NOT_QUALIFIED_FOR_RANKING":
        raise ExecutionValidationError("unqualified_rollout")
    if (
        plan.target_zone != settings.target_zone
        or plan.actuator_identity != settings.actuator_identity
    ):
        raise ExecutionValidationError("actuator_scope_mismatch")
    if any(action.units != settings.units for action in plan.actions):
        raise ExecutionValidationError("unit_mismatch")
    manifest = json.loads((micro.model_directory / "model_manifest.json").read_text())
    first = plan.actions[0]
    memory = SafetyMemory(context.run_id, context.environment_id)
    guard = SafetyGuard(safety, memory)
    proposal = ProposedCommand(
        command_id=f"preflight-{plan.plan_id[:16]}",
        decision_id="module14-preflight",
        run_id=context.run_id,
        environment_id=context.environment_id,
        zone=plan.target_zone,
        actuator=safety.actuator,
        requested_value=first.requested_value,
        source_state_sequence=context.source_state_id,
        decision_sequence=context.source_state_id,
        valid_from_sequence=context.source_state_id + 1,
        expires_after_sequence=context.source_state_id + safety.command_ttl,
        current_sequence=context.source_state_id + 1,
        source_simulation_time_hours=12.25,
        decision_simulation_time_hours=12.25,
        callback_simulation_time_hours=12.5,
    )
    decision, command = guard.evaluate(proposal)
    if command is None:
        raise ExecutionValidationError("failed_first_action_dry_run")
    return {
        "planning_context_id": context.context_id,
        "plan_id": plan.plan_id,
        "strategy": plan.strategy_type,
        "rollout_id": selected_rollout.rollout_id,
        "ledger_evaluation_id": evaluation.evaluation_id,
        "ledger_ranking_id": ranking.ranking_id,
        "plan_fingerprint": plan.plan_fingerprint,
        "rollout_fingerprint": selected_rollout.rollout_fingerprint,
        "ledger_evaluation_fingerprint": evaluation.fingerprint,
        "selected_plan_eligibility": evaluation.eligible,
        "first_action_module8_dry_run": decision.outcome.value,
        "first_action_guard_reason": decision.reason.value,
        "target_zone": plan.target_zone,
        "actuator_identity": plan.actuator_identity,
        "units": first.units,
        "action_count": len(plan.actions),
        "actions": [action.model_dump(mode="json") for action in plan.actions],
        "uncertainty": evaluation.uncertainty,
        "debt_status": evaluation.debt_status,
        "comfort_equity_score": evaluation.comfort_equity_score,
        "opening_thermal_bank_balance": evaluation.bank.opening_balance,
        "closing_thermal_bank_balance": evaluation.bank.closing_balance,
        "model_fingerprint": manifest["model_id"],
        "planning_schema_version": plan.schema_version,
        "microtwin_schema_version": micro.schema_version,
        "ledger_schema_version": evaluation.schema_version,
        "safety_schema_version": safety.schema_version,
        "source_idf_checksum": file_sha256(settings.source_idf),
        "baseline_idf_checksum": file_sha256(settings.baseline_idf),
        "epw_checksum": file_sha256(settings.epw),
    }
