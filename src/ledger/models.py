"""Immutable Comfort Ledger and ledger-aware evaluation schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from src.planning.provenance import planning_fingerprint


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ComfortLedgerEntry(FrozenModel):
    entry_id: str
    account_id: str
    context_id: str
    plan_id: str
    rollout_id: str
    event_id: str | None
    timestep: int
    simulation_timestamp: str
    entry_type: str
    evidence_type: Literal["PREDICTED_LEDGER_ENTRY", "OBSERVED_LEDGER_ENTRY"]
    occupancy: float
    occupied: bool
    protected_event: bool
    lower_boundary_c: float
    upper_boundary_c: float
    predicted_temperature_c: float
    lower_uncertainty_c: float
    upper_uncertainty_c: float
    central_burden: float = Field(ge=0)
    uncertainty_burden: float = Field(ge=0)
    total_burden: float = Field(ge=0)
    credit: float = Field(ge=0)
    debt: float = Field(ge=0)
    repayment: float = Field(ge=0)
    consecutive_burden_count: int = Field(ge=0)
    reason_codes: tuple[str, ...]
    provenance: dict[str, Any]
    schema_version: int = 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fingerprint(self) -> str:
        return planning_fingerprint(self.model_dump(exclude={"fingerprint"}, mode="json"))


class ComfortFairnessAssessment(FrozenModel):
    assessment_id: str
    context_id: str
    plan_id: str
    maximum_event_burden: float
    burden_concentration_ratio: float
    maximum_consecutive_burden: int
    recovery_coverage_ratio: float
    debt_to_credit_ratio: float
    protected_event_burden_count: int
    repeated_burden_selection_count: int
    temporal_burden_variance: float
    event_burden_variance: float
    maximum_debt_age: int
    status: str
    reason_codes: tuple[str, ...]
    limitations: tuple[str, ...] = (
        "deterministic event and temporal fairness proxy",
        "not individual or verified multi-zone fairness",
    )
    schema_version: int = 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fingerprint(self) -> str:
        return planning_fingerprint(self.model_dump(exclude={"fingerprint"}, mode="json"))


class ThermalBankSummary(FrozenModel):
    unit: str = "RTFU"
    opening_balance: float = Field(ge=0)
    deposit: float = Field(ge=0)
    withdrawal: float = Field(ge=0)
    decay: float = Field(ge=0)
    expiry: float = Field(ge=0)
    debt_penalty: float = Field(ge=0)
    uncertainty_reserve: float = Field(ge=0)
    protected_event_reserve: float = Field(ge=0)
    available_balance: float = Field(ge=0)
    closing_balance: float = Field(ge=0)
    reason_codes: tuple[str, ...]


class LedgerPlanEvaluation(FrozenModel):
    evaluation_id: str
    plan_id: str
    rollout_id: str
    context_id: str
    strategy_type: str
    entries: tuple[ComfortLedgerEntry, ...]
    opening_comfort_credit: float = Field(ge=0)
    opening_comfort_debt: float = Field(ge=0)
    new_comfort_burden: float = Field(ge=0)
    comfort_credit: float = Field(ge=0)
    debt_repayment: float = Field(ge=0)
    closing_comfort_debt: float = Field(ge=0)
    debt_status: str
    recovery_obligation: float = Field(ge=0)
    maximum_consecutive_burden: int = Field(ge=0)
    protected_event_burden: float = Field(ge=0)
    fairness: ComfortFairnessAssessment
    comfort_equity_score: float = Field(ge=0, le=100)
    bank: ThermalBankSummary
    blocking_conditions: tuple[str, ...]
    uncertainty: str
    ood_status: str
    advisory_score: float
    microtwin_score: float
    ledger_aware_score: float
    eligible: bool
    rejection_reasons: tuple[str, ...]
    physical_write_performed: bool = False
    schema_version: int = 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fingerprint(self) -> str:
        return planning_fingerprint(self.model_dump(exclude={"fingerprint"}, mode="json"))


class LedgerRanking(FrozenModel):
    ranking_id: str
    context_id: str
    module11_ranking: tuple[str, ...]
    module12_ranking: tuple[str, ...]
    module13_ranking: tuple[str, ...]
    rankings_all_agree: bool
    selected_plan_id: str
    physical_write_performed: bool = False
    schema_version: int = 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fingerprint(self) -> str:
        return planning_fingerprint(self.model_dump(exclude={"fingerprint"}, mode="json"))
