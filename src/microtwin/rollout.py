"""Counterfactual rollouts using only candidate actions and permitted scenarios."""

from __future__ import annotations

import json
import math

from pydantic import BaseModel, ConfigDict, computed_field

from src.microtwin.config import MicroTwinSettings
from src.microtwin.model import load_model
from src.planning.models import CandidatePlan, PlanningContext
from src.planning.provenance import planning_fingerprint


class RolloutPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    timestep: int
    predicted_temperature_c: float
    lower_temperature_c: float
    upper_temperature_c: float
    setpoint_c: float
    expected_occupancy: float
    outdoor_temperature_c: float
    occupied_boundary_risk: bool
    ood_features: tuple[str, ...]


class PlanRollout(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    rollout_id: str
    plan_id: str
    model_id: str
    context_id: str
    points: tuple[RolloutPoint, ...]
    advisory_score: float
    microtwin_score: float
    score_components: dict[str, float]
    ood_feature_count: int
    ood_timestep_count: int
    qualification_status: str
    demand_model_status: str = "UNAVAILABLE"
    physical_write_count: int = 0
    assumptions: tuple[str, ...] = ("offline surrogate estimate", "not EnergyPlus result")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rollout_fingerprint(self) -> str:
        return planning_fingerprint(self.model_dump(exclude={"rollout_fingerprint"}, mode="json"))


def _scenario(context: PlanningContext, kind: str, horizon: int) -> list[float]:
    values = [point.value for point in context.forecasts if point.forecast_type == kind]
    if not values:
        raise ValueError(f"missing {kind} scenario")
    if kind != "WEATHER" or len(values) == 1:
        return [
            values[min(len(values) - 1, index * len(values) // horizon)] for index in range(horizon)
        ]
    result = []
    for index in range(horizon):
        position = index * (len(values) - 1) / max(1, horizon - 1)
        lower = int(position)
        fraction = position - lower
        upper = min(len(values) - 1, lower + 1)
        result.append(values[lower] * (1 - fraction) + values[upper] * fraction)
    return result


def rollout(
    context: PlanningContext, plan: CandidatePlan, settings: MicroTwinSettings
) -> PlanRollout:
    manifest = json.loads((settings.model_directory / "model_manifest.json").read_text())
    if not manifest["thermal_qualification"]:
        raise ValueError("thermal_model_not_qualified")
    model = load_model(settings.model_directory / "thermal_model.json")
    validation = json.loads(
        (settings.model_directory / "thermal_validation_report.json").read_text()
    )
    schema = json.loads((settings.model_directory / "thermal_feature_schema.json").read_text())
    weather, occupancy = (
        _scenario(context, "WEATHER", context.horizon),
        _scenario(context, "OCCUPANCY", context.horizon),
    )
    actions = {action.timestep_offset: action.requested_value for action in plan.actions}
    setpoint = context.current_effective_setpoint_c or 30.0
    predicted, previous = context.current_zone_temperature_c, context.current_zone_temperature_c
    prior_outdoor, prior_setpoint, prior_hvac = weather[0], setpoint, model.means[7]
    points = []
    residual_low, residual_high = validation["residual_p05"], validation["residual_p95"]
    for index in range(1, context.horizon + 1):
        setpoint = actions.get(index, setpoint)
        outdoor, expected = weather[index - 1], occupancy[index - 1]
        hour = 12.25 + index * context.timestep_minutes / 60
        features = (
            predicted,
            predicted - previous,
            outdoor,
            outdoor - prior_outdoor,
            setpoint,
            setpoint - prior_setpoint,
            expected,
            prior_hvac,
            0.0,
            math.sin(2 * math.pi * hour / 24),
            math.cos(2 * math.pi * hour / 24),
        )
        ood = tuple(
            name
            for name, value, low, high in zip(
                model.feature_names,
                features,
                schema["training_minimums"],
                schema["training_maximums"],
                strict=True,
            )
            if value < low - abs(low) * settings.ood_tolerance_fraction
            or value > high + abs(high) * settings.ood_tolerance_fraction
        )
        previous, predicted = predicted, model.predict(features)
        expansion = math.sqrt(index)
        lower, upper = predicted + residual_low * expansion, predicted + residual_high * expansion
        risk = expected > 0 and (
            lower < settings.occupied_lower_c or upper > settings.occupied_upper_c
        )
        points.append(
            RolloutPoint(
                timestep=index,
                predicted_temperature_c=predicted,
                lower_temperature_c=lower,
                upper_temperature_c=upper,
                setpoint_c=setpoint,
                expected_occupancy=expected,
                outdoor_temperature_c=outdoor,
                occupied_boundary_risk=risk,
                ood_features=ood,
            )
        )
        prior_outdoor, prior_setpoint = outdoor, setpoint
    ood_count = sum(len(point.ood_features) for point in points)
    risk_count = sum(point.occupied_boundary_risk for point in points)
    proximity = sum(
        max(0.0, point.upper_temperature_c - (settings.occupied_upper_c - 1.0))
        for point in points
        if point.expected_occupancy > 0
    )
    components = {
        "temperature_risk": risk_count * 10.0 + proximity,
        "uncertainty": sum(
            point.upper_temperature_c - point.lower_temperature_c for point in points
        ),
        "demand_proxy": 0.0,
        "peak_proxy": 0.0,
        "churn": max(0, len(plan.actions) - 1) * 0.5,
        "ood": ood_count * 20.0,
    }
    score = round(sum(components.values()), 6)
    rollout_id = planning_fingerprint(
        {"model": manifest["model_id"], "plan": plan.plan_id, "context": context.context_id}
    )
    return PlanRollout(
        rollout_id=rollout_id,
        plan_id=plan.plan_id,
        model_id=manifest["model_id"],
        context_id=context.context_id,
        points=tuple(points),
        advisory_score=plan.advisory_score,
        microtwin_score=score,
        score_components=components,
        ood_feature_count=ood_count,
        ood_timestep_count=sum(bool(point.ood_features) for point in points),
        qualification_status=(
            "QUALIFIED"
            if ood_count == 0
            else (
                "NOT_QUALIFIED_FOR_RANKING"
                if sum(bool(point.ood_features) for point in points) >= context.horizon // 2
                else "QUALIFIED_WITH_OOD_WARNING"
            )
        ),
    )


def rank_rollouts(items: tuple[PlanRollout, ...]) -> tuple[PlanRollout, ...]:
    eligible = [item for item in items if item.qualification_status != "NOT_QUALIFIED_FOR_RANKING"]
    return tuple(sorted(eligible, key=lambda item: (item.microtwin_score, item.plan_id)))
