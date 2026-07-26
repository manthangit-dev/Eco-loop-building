"""Deterministic bounded strategy templates and candidate generation."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.control.models import ActuatorIdentity
from src.planning.config import PlanningSettings
from src.planning.models import CandidateAction, CandidatePlan, PlanningContext
from src.planning.provenance import planning_fingerprint
from src.planning.scoring import score
from src.planning.validator import validate_actions
from src.safety.config import load_safety_settings
from src.safety.guard import SafetyGuard
from src.safety.memory import SafetyMemory
from src.safety.models import ProposedCommand


def _timestamp(context: PlanningContext, offset: int) -> str:
    value = datetime.strptime(context.planning_timestamp, "%m-%d %H:%M")
    return (value + timedelta(minutes=context.timestep_minutes * offset)).strftime("%m-%d %H:%M")


def _action(
    context: PlanningContext, strategy: str, sequence: int, offset: int, value: float, kind: str
) -> CandidateAction:
    return CandidateAction(
        action_sequence=sequence,
        timestep_offset=offset,
        intended_simulation_timestamp=_timestamp(context, offset),
        actuator_identity=context.actuator_identity,
        requested_value=round(value, 2),
        action_type=kind,
        source_template=strategy,
        rationale_code=f"{strategy.lower()}_{kind.lower()}",
    )


def _guard(
    context: PlanningContext, settings: PlanningSettings, action: CandidateAction
) -> tuple[str, str]:
    actuator = ActuatorIdentity("Zone Temperature Control", "Cooling Setpoint", "SPACE3-1", "C")
    source, current = context.source_state_id, context.source_state_id + 1
    proposal = ProposedCommand(
        f"plan-{context.context_id[:12]}-{action.source_template}",
        "module11-dry-run",
        context.run_id,
        context.environment_id,
        context.target_zone,
        actuator,
        action.requested_value,
        source,
        source,
        current,
        current + 1,
        current,
        source / 4,
        source / 4,
        current / 4,
    )
    safety = load_safety_settings(settings.root / "config/safety_guard.yaml")
    decision, _ = SafetyGuard(
        safety, SafetyMemory(context.run_id, context.environment_id)
    ).evaluate(proposal)
    return decision.outcome.value, decision.reason.value


def generate_plans(
    context: PlanningContext, settings: PlanningSettings, permitted: tuple[str, ...] | None = None
) -> tuple[CandidatePlan, ...]:
    current = context.current_effective_setpoint_c or 30.0
    peak = any(
        point.forecast_type in {"TARIFF", "CARBON"} and point.value >= 1.5
        for point in context.forecasts
    )
    future_occupied = any(
        point.forecast_type == "OCCUPANCY" and point.value > 0 for point in context.forecasts
    )
    templates: dict[str, tuple[CandidateAction, ...]] = {
        "NATIVE_HOLD": (_action(context, "NATIVE_HOLD", 0, 1, current, "HOLD"),),
        "COMFORT_FIRST": (
            _action(
                context, "COMFORT_FIRST", 0, 1, max(settings.minimum_celsius, current - 1.5), "SET"
            ),
        ),
        "BALANCED": (
            _action(context, "BALANCED", 0, 1, max(settings.minimum_celsius, current - 1.0), "SET"),
        ),
    }
    if peak and future_occupied:
        templates["PRECONDITION_BEFORE_PEAK"] = (
            _action(context, "PRECONDITION_BEFORE_PEAK", 0, 1, current - 1.5, "PRECONDITION"),
            _action(context, "PRECONDITION_BEFORE_PEAK", 1, 6, current, "RESTORE"),
        )
    if context.current_occupancy == 0 and future_occupied:
        templates["VACANCY_RELAXATION"] = (
            _action(context, "VACANCY_RELAXATION", 0, 1, current, "RELAX"),
            _action(context, "VACANCY_RELAXATION", 1, 4, current - 1.5, "RESTORE"),
        )
    if context.current_occupancy > 0 and context.current_zone_temperature_c > 27:
        templates["OCCUPIED_RECOVERY"] = (
            _action(context, "OCCUPIED_RECOVERY", 0, 1, current - 1.5, "RECOVER"),
        )
    allowed = set(permitted or settings.strategies)
    plans = []
    for strategy in sorted(templates):
        if strategy not in allowed:
            continue
        actions = templates[strategy]
        errors = validate_actions(context, settings, strategy, actions)
        outcome, reason = _guard(context, settings, actions[0])
        guard_ok = outcome in {"ALLOW", "CLAMP", "HOLD_LAST_SAFE", "RESET_TO_NATIVE"}
        components, total = score(context, strategy, actions, guard_ok)
        eligible = not errors and guard_ok
        plan_id = planning_fingerprint(
            {
                "context": context.context_id,
                "strategy": strategy,
                "actions": [a.model_dump(mode="json") for a in actions],
            }
        )
        plans.append(
            CandidatePlan(
                plan_id=plan_id,
                context_id=context.context_id,
                strategy_type=strategy,
                target_zone=context.target_zone,
                actuator_identity=context.actuator_identity,
                start_timestamp=actions[0].intended_simulation_timestamp,
                horizon=context.horizon,
                actions=actions,
                expected_intent=strategy.replace("_", " ").title(),
                assumptions=("local scenario inputs only", "no physical trajectory prediction"),
                constraints=("advisory only", "execution-time guard required"),
                uncertainty=context.uncertainty,
                first_action_guard_outcome=outcome,
                first_action_guard_reason=reason,
                validation_status="PASS" if not errors else "REJECTED",
                score_components=components,
                advisory_score=total,
                eligible=eligible,
                rejection_reasons=errors + (() if guard_ok else ("first_action_guard_rejected",)),
            )
        )
    return tuple(
        sorted(
            plans,
            key=lambda plan: (
                not plan.eligible,
                plan.advisory_score,
                plan.strategy_type,
                plan.plan_id,
            ),
        )[: settings.candidate_limit]
    )


def select_deterministic(plans: tuple[CandidatePlan, ...]) -> CandidatePlan:
    eligible = [plan for plan in plans if plan.eligible]
    if not eligible:
        raise ValueError("no eligible candidate")
    return min(eligible, key=lambda plan: (plan.advisory_score, plan.strategy_type, plan.plan_id))
