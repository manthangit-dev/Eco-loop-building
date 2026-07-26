"""Strict Module 10 supervisor schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ObjectiveType(StrEnum):
    DESCRIBE_CURRENT_STATE = "DESCRIBE_CURRENT_STATE"
    EXPLAIN_CONTROLLER_STATUS = "EXPLAIN_CONTROLLER_STATUS"
    EXPLAIN_SAFETY_STATUS = "EXPLAIN_SAFETY_STATUS"
    INVESTIGATE_ENERGYPLUS_ERRORS = "INVESTIGATE_ENERGYPLUS_ERRORS"
    COMPARE_RECORDED_RUNS = "COMPARE_RECORDED_RUNS"
    SUMMARISE_RECENT_ZONE_HISTORY = "SUMMARISE_RECENT_ZONE_HISTORY"
    ASSESS_CONTROL_PROPOSAL_DRY_RUN = "ASSESS_CONTROL_PROPOSAL_DRY_RUN"
    EXPLAIN_REJECTED_PROPOSAL = "EXPLAIN_REJECTED_PROPOSAL"
    GENERAL_BUILDING_DIAGNOSTIC = "GENERAL_BUILDING_DIAGNOSTIC"
    EXPLAIN_FORECAST_CONTEXT = "EXPLAIN_FORECAST_CONTEXT"
    GENERATE_CANDIDATE_PLANS = "GENERATE_CANDIDATE_PLANS"
    COMPARE_CANDIDATE_PLANS = "COMPARE_CANDIDATE_PLANS"
    RECOMMEND_ADVISORY_PLAN = "RECOMMEND_ADVISORY_PLAN"
    EXPLAIN_PLAN_REJECTION = "EXPLAIN_PLAN_REJECTION"
    EXPLAIN_PLAN_UNCERTAINTY = "EXPLAIN_PLAN_UNCERTAINTY"
    EXPLAIN_MICROTWIN_STATUS = "EXPLAIN_MICROTWIN_STATUS"
    EXPLAIN_MICROTWIN_VALIDATION = "EXPLAIN_MICROTWIN_VALIDATION"
    EVALUATE_PLAN_WITH_MICROTWIN = "EVALUATE_PLAN_WITH_MICROTWIN"
    COMPARE_MICROTWIN_ROLLOUTS = "COMPARE_MICROTWIN_ROLLOUTS"
    RECOMMEND_MICROTWIN_RANKED_PLAN = "RECOMMEND_MICROTWIN_RANKED_PLAN"
    EXPLAIN_RANKING_DIFFERENCE = "EXPLAIN_RANKING_DIFFERENCE"
    EXPLAIN_MICROTWIN_UNCERTAINTY = "EXPLAIN_MICROTWIN_UNCERTAINTY"
    EXPLAIN_COMFORT_LEDGER = "EXPLAIN_COMFORT_LEDGER"
    EXPLAIN_COMFORT_DEBT = "EXPLAIN_COMFORT_DEBT"
    EXPLAIN_RECOVERY_OBLIGATION = "EXPLAIN_RECOVERY_OBLIGATION"
    COMPARE_COMFORT_LEDGER_PLANS = "COMPARE_COMFORT_LEDGER_PLANS"
    EXPLAIN_COMFORT_EQUITY_SCORE = "EXPLAIN_COMFORT_EQUITY_SCORE"
    EXPLAIN_THERMAL_BANK = "EXPLAIN_THERMAL_BANK"
    COMPARE_THERMAL_BANK_PLANS = "COMPARE_THERMAL_BANK_PLANS"
    RECOMMEND_LEDGER_AWARE_PLAN = "RECOMMEND_LEDGER_AWARE_PLAN"
    EXPLAIN_LEDGER_LIMITATIONS = "EXPLAIN_LEDGER_LIMITATIONS"
    EXPLAIN_EXECUTION_APPROVAL = "EXPLAIN_EXECUTION_APPROVAL"
    EXPLAIN_EXECUTION_STATUS = "EXPLAIN_EXECUTION_STATUS"
    EXPLAIN_EXECUTION_FALLBACK = "EXPLAIN_EXECUTION_FALLBACK"
    EXPLAIN_EXECUTION_AUDIT = "EXPLAIN_EXECUTION_AUDIT"
    COMPARE_SHORT_EXECUTION_RUNS = "COMPARE_SHORT_EXECUTION_RUNS"
    EXPLAIN_SIMULATION_RECONCILIATION = "EXPLAIN_SIMULATION_RECONCILIATION"


class SupervisorRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request_id: str = Field(min_length=1, max_length=128)
    objective_type: ObjectiveType
    objective_text: str = Field(min_length=1, max_length=2000)
    run_id: str
    environment_id: str | None = None
    state_id: int | None = Field(default=None, gt=0)
    simulation_timestamp: str | None = None
    zone: str | None = None
    allowed_metrics: tuple[str, ...] = Field(default=(), max_length=20)
    proposal_value: float | None = None
    proposal_units: str | None = None
    candidate_plan_ids: tuple[str, ...] = Field(default=(), max_length=12)
    selected_plan_id: str | None = None
    dry_run_only: bool = True
    response_detail: str = "bounded"
    schema_version: int = 1

    @model_validator(mode="after")
    def safety(self) -> SupervisorRequest:
        if not self.dry_run_only or self.schema_version != 1:
            raise ValueError("Module 10 requests must be schema-v1 dry runs")
        return self


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    tool_name: str
    tool_call_id: str
    run_id: str | None = None
    state_id: int | None = None
    metric: str
    observed_value: Any
    provenance: dict[str, Any] = Field(default_factory=dict)


class ToolStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    tool_name: str
    tool_call_id: str
    success: bool
    reused: bool = False
    execution_mode: str = "MODEL_SELECTED_TOOL"


class SupervisorResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    session_id: str
    request_id: str
    objective_type: ObjectiveType
    status: str
    summary: str = Field(max_length=4000)
    evidence: tuple[Evidence, ...] = ()
    tool_calls: tuple[ToolStep, ...] = ()
    warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    recommended_next_step: str
    control_proposal: dict[str, Any] | None = None
    physical_write_performed: bool = False
    confidence_category: str = "BOUNDED_EVIDENCE"
    provider: str
    model: str
    schema_version: int = 1

    @model_validator(mode="after")
    def no_physical_claim(self) -> SupervisorResponse:
        if self.physical_write_performed:
            raise ValueError("Module 10 cannot claim a physical write")
        lowered = self.summary.lower()
        forbidden = ("verified savings", "comfort improved", "physical write performed")
        if any(term in lowered for term in forbidden):
            raise ValueError("unsupported claim")
        return self
