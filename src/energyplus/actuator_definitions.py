"""Frozen configuration for the one approved Module 5 actuator."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


class ActuatorScope(StrEnum):
    ZONE = "zone"


@dataclass(frozen=True)
class ActuatorDefinition:
    logical_id: str
    display_name: str
    component_type: str
    control_type: str
    unique_key: str
    units: str
    scope: ActuatorScope
    target_zone: str
    zone_specific: bool
    shared_resource: bool
    minimum: float
    maximum: float
    maximum_offset: float
    required: bool
    discovery_source: str
    eligible: bool
    rejection_reason: str = ""

    def __post_init__(self) -> None:
        if not self.component_type or not self.control_type or not self.unique_key:
            raise ValueError("Actuator component type, control type, and key are required.")
        if self.target_zone.upper().startswith("PLENUM"):
            raise ValueError("A plenum cannot be the Module 5 target.")
        if self.shared_resource or not self.zone_specific:
            raise ValueError("Module 5 requires an isolated zone actuator.")
        if self.units not in {"C", "[C]"}:
            raise ValueError("Only a Celsius cooling set-point actuator is supported.")
        if self.minimum >= self.maximum or self.maximum_offset <= 0:
            raise ValueError("Actuator bounds and maximum offset are invalid.")


@dataclass(frozen=True)
class ActuatorSettings:
    root: Path
    output_root: Path
    control_output: Path
    intervention_output: Path
    discovery_csv: str
    event_jsonl: str
    event_csv: str
    manifest_json: str
    summary_json: str
    validation_json: str
    comparison_json: str
    effective_setpoint_variable: str
    weather_environment_type: int
    definition: ActuatorDefinition
    raw: dict[str, Any]


def load_actuator_settings(path: Path, root: Path) -> ActuatorSettings:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    test = raw["actuator_test"]
    safety = raw["safety"]
    forbidden = [key for key, value in safety.items() if key.startswith("allow_") and value]
    if test["experiment_type"] != "deterministic_single_zone_setpoint_test":
        raise ValueError("Unsupported actuator experiment type.")
    if int(safety["maximum_actuators"]) != 1 or forbidden:
        raise ValueError("Module 5 safety configuration permits unsupported access.")
    target = raw["target"]
    intervention = raw["intervention"]
    definition = ActuatorDefinition(
        logical_id="target_zone_cooling_setpoint",
        display_name="Target-zone cooling set-point",
        component_type=str(target["component_type"]),
        control_type=str(target["control_type"]),
        unique_key=str(target["unique_key"]),
        units=str(target["units"]),
        scope=ActuatorScope.ZONE,
        target_zone=str(target["zone_name"]),
        zone_specific=True,
        shared_resource=False,
        minimum=float(intervention["minimum_setpoint_celsius"]),
        maximum=float(intervention["maximum_setpoint_celsius"]),
        maximum_offset=float(intervention["maximum_offset_celsius"]),
        required=True,
        discovery_source="Runtime API catalog",
        eligible=True,
    )
    output_root_raw = Path(str(test["output_root"]))
    if output_root_raw.is_absolute():
        raise ValueError("Actuator output root must be repository-relative.")
    output_root = (root / output_root_raw).resolve()
    return ActuatorSettings(
        root=root,
        output_root=output_root,
        control_output=(output_root / str(test["control_run_directory"])).resolve(),
        intervention_output=(output_root / str(test["intervention_run_directory"])).resolve(),
        discovery_csv=str(test["discovery_csv"]),
        event_jsonl=str(test["event_jsonl"]),
        event_csv=str(test["event_csv"]),
        manifest_json=str(test["manifest_json"]),
        summary_json=str(test["summary_json"]),
        validation_json=str(test["validation_json"]),
        comparison_json=str(test["comparison_json"]),
        effective_setpoint_variable=str(target["effective_setpoint_variable"]),
        weather_environment_type=3,
        definition=definition,
        raw=raw,
    )
