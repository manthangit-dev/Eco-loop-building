"""Versioned Thermal Bank configuration."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ThermalBankSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: int
    enabled: bool
    advisory_only: bool
    target_zone: str
    unit: str
    maximum_balance: float = Field(gt=0)
    minimum_balance: float = Field(ge=0)
    overdraft_allowed: bool
    maximum_deposit_per_timestep: float = Field(ge=0)
    maximum_deposit_per_horizon: float = Field(ge=0)
    deposit_expiry_timesteps: int = Field(gt=0)
    deposit_decay_fraction: float = Field(ge=0, le=1)
    withdrawal_limit_per_timestep: float = Field(ge=0)
    withdrawal_limit_per_event: float = Field(ge=0)
    recovery_reserve: float = Field(ge=0)
    uncertainty_reserve_fraction: float = Field(ge=0, le=1)
    protected_event_reserve: float = Field(ge=0)
    credit_to_bank_conversion: float = Field(ge=0)
    debt_to_bank_penalty: float = Field(ge=0)
    microtwin_qualification_required: bool
    strong_ood_policy: str
    missing_demand_model_policy: str
    persistence_enabled: bool
    replay_enabled: bool

    @model_validator(mode="after")
    def validate_policy(self) -> ThermalBankSettings:
        if self.schema_version != 1 or not self.enabled or not self.advisory_only:
            raise ValueError("thermal bank must be enabled schema-v1 advisory-only")
        if self.target_zone == "PLENUM-1" or self.unit != "RTFU":
            raise ValueError("invalid thermal bank target or unit")
        if self.overdraft_allowed or self.minimum_balance != 0:
            raise ValueError("overdraft is prohibited")
        return self


def load_thermal_bank_settings(path: Path) -> ThermalBankSettings:
    return ThermalBankSettings.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
