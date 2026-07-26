"""Validated Module 14 configuration."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.execution.models import ExecutionMode


class ExecutionSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    root: Path
    schema_version: int
    approval_schema_version: int
    default_mode: ExecutionMode
    live_mode_enabled_by_default: bool
    simulation_only: bool
    public_listener_allowed: bool
    target_zone: str
    actuator_identity: str
    units: str
    maximum_actions: int = Field(gt=0)
    maximum_writes: int = Field(gt=0)
    maximum_resets: int = Field(gt=0)
    timeout_seconds: int = Field(gt=0)
    state_max_age_seconds: int = Field(gt=0)
    minimum_hold_timesteps: int = Field(ge=1)
    permitted_environment: str
    source_idf: Path
    baseline_idf: Path
    epw: Path
    database: Path
    output_root: Path

    @model_validator(mode="after")
    def boundary(self) -> ExecutionSettings:
        if self.schema_version != 1 or self.approval_schema_version != 1:
            raise ValueError("unsupported_execution_schema")
        if self.live_mode_enabled_by_default or not self.simulation_only:
            raise ValueError("simulation_only_fail_closed")
        if self.public_listener_allowed:
            raise ValueError("public_execution_listener_rejected")
        if self.target_zone != "SPACE3-1" or self.units != "C":
            raise ValueError("approved_actuator_scope_mismatch")
        return self


def load_execution_settings(path: Path) -> ExecutionSettings:
    root = path.resolve().parents[1]
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    execution, artifacts, output = raw["execution"], raw["artifacts"], raw["output"]
    return ExecutionSettings(
        root=root,
        **execution,
        source_idf=root / artifacts["source_idf"],
        baseline_idf=root / artifacts["baseline_idf"],
        epw=root / artifacts["epw"],
        database=root / artifacts["database"],
        output_root=root / output["root"],
    )
