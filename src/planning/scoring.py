"""Transparent dimensionless advisory scoring; lower is better."""

from src.planning.models import CandidateAction, PlanningContext


def score(
    context: PlanningContext, strategy: str, actions: tuple[CandidateAction, ...], guard_ok: bool
) -> tuple[dict[str, float], float]:
    current = context.current_effective_setpoint_c or 30.0
    peak = any(point.forecast_type == "TARIFF" and point.value >= 3 for point in context.forecasts)
    occupied = any(
        point.forecast_type == "OCCUPANCY" and point.value > 0 for point in context.forecasts
    )
    components = {
        "intervention": round(sum(abs(action.requested_value - current) for action in actions), 3),
        "churn": float(max(0, len(actions) - 1)) * 0.5,
        "occupancy_risk": 2.0 if occupied and strategy == "VACANCY_RELAXATION" else 0.0,
        "peak_alignment": -1.0 if peak and strategy == "PRECONDITION_BEFORE_PEAK" else 0.0,
        "uncertainty": 1.0 if context.uncertainty == "HIGH" else 0.5,
        "missing_data": float(len(context.missing_data)) * 2.0,
        "guard_rejection": 0.0 if guard_ok else 100.0,
    }
    return components, round(sum(components.values()), 3)
