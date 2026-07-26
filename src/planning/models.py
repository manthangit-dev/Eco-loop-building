"""Immutable planning schemas with stable fingerprints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field

from src.planning.provenance import planning_fingerprint


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ForecastPoint(FrozenModel):
    forecast_type: str
    sequence: int
    simulation_timestamp: str
    zone: str | None = None
    value: float
    units: str
    uncertainty: str
    source: str
    provenance: dict[str, Any]


class BuildingEvent(FrozenModel):
    start_timestamp: str
    end_timestamp: str
    zone: str
    event_type: str
    priority: str
    comfort_protection: bool
    source: str
    uncertainty: str


class PlanningContext(FrozenModel):
    context_id: str
    run_id: str
    environment_id: str
    source_state_id: int
    planning_timestamp: str
    target_zone: str
    actuator_identity: str
    current_zone_temperature_c: float
    current_effective_setpoint_c: float | None
    current_occupancy: float
    current_controller_mode: str | None
    current_safety_status: str
    horizon: int
    timestep_minutes: int
    forecasts: tuple[ForecastPoint, ...]
    events: tuple[BuildingEvent, ...]
    missing_data: tuple[str, ...] = ()
    uncertainty: str = "MEDIUM"
    source_checksums: dict[str, str]
    prohibited_future_source_count: int = 0
    schema_version: int = 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def context_fingerprint(self) -> str:
        return planning_fingerprint(self.model_dump(exclude={"context_fingerprint"}, mode="json"))


class CandidateAction(FrozenModel):
    action_sequence: int
    timestep_offset: int
    intended_simulation_timestamp: str
    actuator_identity: str
    requested_value: float
    units: str = "C"
    action_type: str
    source_template: str
    rationale_code: str
    advisory_only: bool = True
    requires_execution_time_guard_validation: bool = True


class CandidatePlan(FrozenModel):
    plan_id: str
    context_id: str
    strategy_type: str
    target_zone: str
    actuator_identity: str
    start_timestamp: str
    horizon: int
    actions: tuple[CandidateAction, ...]
    expected_intent: str
    assumptions: tuple[str, ...]
    constraints: tuple[str, ...]
    uncertainty: str
    first_action_guard_outcome: str
    first_action_guard_reason: str
    validation_status: str
    score_components: dict[str, float]
    advisory_score: float
    eligible: bool
    rejection_reasons: tuple[str, ...] = ()
    schema_version: int = 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def plan_fingerprint(self) -> str:
        return planning_fingerprint(self.model_dump(exclude={"plan_fingerprint"}, mode="json"))


class PlanSelection(FrozenModel):
    context_id: str
    deterministic_plan_id: str
    llm_plan_id: str | None = None
    agreement: bool | None = None
    advisory_only: bool = True
    physical_write_performed: bool = False
