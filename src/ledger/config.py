"""Versioned Comfort Ledger configuration."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ComfortLedgerSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: int
    enabled: bool
    advisory_only: bool
    allowed_zones: tuple[str, ...]
    target_zone: str
    boundary_source: str
    occupied_lower_c: float
    occupied_upper_c: float
    unoccupied_lower_c: float
    unoccupied_upper_c: float
    protected_event_lower_c: float
    protected_event_upper_c: float
    uncertainty_policy: str
    burden_method: str
    credit_method: str
    debt_method: str
    debt_ageing_per_timestep: int = Field(ge=0)
    debt_decay_fraction: float = Field(ge=0, le=1)
    debt_expiry_timesteps: int = Field(gt=0)
    repayment_fraction: float = Field(ge=0, le=1)
    consecutive_burden_limit: int = Field(gt=0)
    maximum_horizon_burden: float = Field(gt=0)
    maximum_debt: float = Field(gt=0)
    minimum_recovery: float = Field(ge=0)
    maximum_credit_per_timestep: float = Field(ge=0)
    maximum_credit_per_horizon: float = Field(ge=0)
    credit_decay_fraction: float = Field(ge=0, le=1)
    credit_expiry_timesteps: int = Field(gt=0)
    fairness_windows: int = Field(gt=0)
    missing_occupancy_policy: str
    missing_temperature_policy: str
    missing_uncertainty_policy: str
    persistence_enabled: bool
    replay_enabled: bool
    equity_weights: dict[str, float]

    @model_validator(mode="after")
    def validate_policy(self) -> ComfortLedgerSettings:
        if self.schema_version != 1 or not self.enabled or not self.advisory_only:
            raise ValueError("comfort ledger must be enabled schema-v1 advisory-only")
        if self.target_zone not in self.allowed_zones or "PLENUM-1" in self.allowed_zones:
            raise ValueError("invalid target zone")
        pairs = (
            (self.occupied_lower_c, self.occupied_upper_c),
            (self.unoccupied_lower_c, self.unoccupied_upper_c),
            (self.protected_event_lower_c, self.protected_event_upper_c),
        )
        if any(lower >= upper for lower, upper in pairs):
            raise ValueError("invalid temperature boundaries")
        if abs(sum(self.equity_weights.values()) - 1.0) > 1e-9:
            raise ValueError("equity weights must sum to one")
        return self


def load_comfort_ledger_settings(path: Path) -> ComfortLedgerSettings:
    return ComfortLedgerSettings.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
