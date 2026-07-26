"""Planning consistency validation, separate from Module 8 authority."""

import math

from src.planning.config import PlanningSettings
from src.planning.models import CandidateAction, PlanningContext


def validate_actions(
    context: PlanningContext,
    settings: PlanningSettings,
    strategy: str,
    actions: tuple[CandidateAction, ...],
) -> tuple[str, ...]:
    errors: list[str] = []
    if context.target_zone not in settings.allowed_zones:
        errors.append("unapproved_zone")
    if strategy not in settings.strategies:
        errors.append("unsupported_strategy")
    if not actions or len(actions) > settings.action_limit:
        errors.append("invalid_action_count")
    offsets = [action.timestep_offset for action in actions]
    if offsets != sorted(offsets) or len(offsets) != len(set(offsets)):
        errors.append("invalid_action_order")
    previous = context.current_effective_setpoint_c or settings.maximum_celsius
    for action in actions:
        if action.actuator_identity != context.actuator_identity or action.units != "C":
            errors.append("unapproved_actuator")
        if not math.isfinite(action.requested_value):
            errors.append("non_finite_value")
        elif not settings.minimum_celsius <= action.requested_value <= settings.maximum_celsius:
            errors.append("absolute_bound_violation")
        elif abs(action.requested_value - previous) > settings.maximum_change_celsius + 1e-9:
            errors.append("planned_rate_limit")
        if not action.advisory_only or not action.requires_execution_time_guard_validation:
            errors.append("execution_authority_forbidden")
        previous = action.requested_value
    if strategy in {"PRECONDITION_BEFORE_PEAK", "VACANCY_RELAXATION"} and len(actions) < 2:
        errors.append("missing_restoration_action")
    return tuple(dict.fromkeys(errors))
