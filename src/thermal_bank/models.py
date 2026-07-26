"""Immutable Thermal Bank transaction schema."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from src.planning.provenance import planning_fingerprint


class ThermalBankTransaction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    transaction_id: str
    account_id: str
    sequence: int = Field(gt=0)
    planning_timestamp: str
    transaction_type: Literal[
        "DEPOSIT",
        "WITHDRAWAL",
        "DECAY",
        "EXPIRY",
        "DEBT_PENALTY",
        "UNCERTAINTY_RESERVE",
        "PROTECTED_EVENT_RESERVE",
        "RECOVERY_RELEASE",
        "REVERSAL",
    ]
    amount: float = Field(ge=0)
    opening_balance: float = Field(ge=0)
    closing_balance: float = Field(ge=0)
    source_plan_id: str
    source_rollout_id: str
    source_event_id: str | None = None
    expiry_timestamp: str | None = None
    reason_code: str
    provenance: dict[str, Any]
    advisory_only: bool = True
    schema_version: int = 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fingerprint(self) -> str:
        return planning_fingerprint(self.model_dump(exclude={"fingerprint"}, mode="json"))
