"""Validated Module 11 planning configuration."""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PlanningSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    root: Path
    schema_version: int
    enabled: bool
    advisory_only: bool
    timestep_minutes: int = Field(gt=0)
    minimum_horizon: int = Field(ge=1)
    default_horizon: int
    maximum_horizon: int = Field(le=96)
    candidate_limit: int = Field(ge=1, le=12)
    action_limit: int = Field(ge=1, le=8)
    strategies: tuple[str, ...]
    allowed_zones: tuple[str, ...]
    actuator: dict[str, str]
    minimum_celsius: float
    maximum_celsius: float
    maximum_change_celsius: float
    weights: dict[str, float]
    sources: dict[str, Path]
    output_root: Path
    database: Path
    database_schema_version: int

    @model_validator(mode="after")
    def safe(self) -> "PlanningSettings":
        if not self.enabled or not self.advisory_only or self.schema_version != 1:
            raise ValueError("planning must be schema-v1 advisory-only")
        if not self.minimum_horizon <= self.default_horizon <= self.maximum_horizon:
            raise ValueError("invalid planning horizon")
        if self.database_schema_version != 6 or "SPACE3-1" not in self.allowed_zones:
            raise ValueError("invalid planning authority")
        return self


def load_planning_settings(path: Path) -> PlanningSettings:
    root = path.resolve().parents[1]
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    p, storage = raw["planning"], raw["storage"]
    return PlanningSettings(
        root=root,
        schema_version=p["schema_version"],
        enabled=p["enabled"],
        advisory_only=p["advisory_only"],
        timestep_minutes=p["timestep_minutes"],
        minimum_horizon=p["horizon"]["minimum"],
        default_horizon=p["horizon"]["default"],
        maximum_horizon=p["horizon"]["maximum"],
        candidate_limit=p["candidate_limit"],
        action_limit=p["action_limit_per_plan"],
        strategies=tuple(p["supported_strategies"]),
        allowed_zones=tuple(p["allowed_zones"]),
        actuator=p["actuator"],
        minimum_celsius=p["limits"]["minimum_celsius"],
        maximum_celsius=p["limits"]["maximum_celsius"],
        maximum_change_celsius=p["limits"]["maximum_change_celsius"],
        weights=p["score_weights"],
        sources={k: root / v for k, v in raw["sources"].items()},
        output_root=root / storage["output_root"],
        database=root / storage["output_root"] / storage["database"],
        database_schema_version=storage["schema_version"],
    )
