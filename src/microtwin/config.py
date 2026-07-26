from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, model_validator


class MicroTwinSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    root: Path
    schema_version: int
    enabled: bool
    advisory_only: bool
    model_family: str
    source_run: str
    environment_id: str
    target_zone: str
    ridge_alpha: float
    train_fraction: float
    validation_fraction: float
    test_fraction: float
    feature_order: tuple[str, ...]
    minimum_improvement: float
    maximum_12_step_mae_c: float
    prohibited_feature_count: int
    ood_tolerance_fraction: float
    occupied_lower_c: float
    occupied_upper_c: float
    score_weights: dict[str, float]
    output_root: Path
    model_directory: Path
    database: Path
    database_schema_version: int

    @model_validator(mode="after")
    def safe(self) -> "MicroTwinSettings":
        if not self.enabled or not self.advisory_only or self.schema_version != 1:
            raise ValueError("MicroTwin must be schema-v1 advisory-only")
        if abs(self.train_fraction + self.validation_fraction + self.test_fraction - 1) > 1e-9:
            raise ValueError("chronological split fractions must sum to one")
        if self.prohibited_feature_count != 0 or self.database_schema_version != 7:
            raise ValueError("invalid causal/schema configuration")
        return self


def load_microtwin_settings(path: Path) -> MicroTwinSettings:
    root = path.resolve().parents[1]
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    m, storage = raw["microtwin"], raw["storage"]
    return MicroTwinSettings(
        root=root,
        schema_version=m["schema_version"],
        enabled=m["enabled"],
        advisory_only=m["advisory_only"],
        model_family=m["model_family"],
        source_run=m["source_run"],
        environment_id=m["environment_id"],
        target_zone=m["target_zone"],
        ridge_alpha=m["ridge_alpha"],
        train_fraction=m["split"]["train"],
        validation_fraction=m["split"]["validation"],
        test_fraction=m["split"]["test"],
        feature_order=tuple(m["feature_order"]),
        minimum_improvement=m["qualification"]["minimum_mae_improvement_fraction"],
        maximum_12_step_mae_c=m["qualification"]["maximum_12_step_mae_c"],
        prohibited_feature_count=m["qualification"]["prohibited_feature_count"],
        ood_tolerance_fraction=m["ood_tolerance_fraction"],
        occupied_lower_c=m["comfort_proxy"]["occupied_lower_c"],
        occupied_upper_c=m["comfort_proxy"]["occupied_upper_c"],
        score_weights=m["score_weights"],
        output_root=root / storage["output_root"],
        model_directory=root / storage["output_root"] / storage["model_directory"],
        database=root / storage["database"],
        database_schema_version=storage["database_schema_version"],
    )
