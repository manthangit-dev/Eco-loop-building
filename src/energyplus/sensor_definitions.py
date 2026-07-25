"""Immutable read-only sensor definitions loaded from Module 4 configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


class ExchangeKind(StrEnum):
    VARIABLE = "Variable"
    METER = "Meter"
    SIMULATION_TIME = "SimulationTime"


class SensorScope(StrEnum):
    BUILDING = "building"
    ENVIRONMENT = "environment"
    ZONE = "zone"


@dataclass(frozen=True)
class SensorDefinition:
    logical_id: str
    display_name: str
    exchange_kind: ExchangeKind
    name: str
    key: str
    units: str
    scope: SensorScope
    required: bool
    expected_value_type: str = "float"
    minimum: float | None = None
    maximum: float | None = None
    description: str = ""
    enabled: bool = True
    unavailable_reason: str = ""
    fallback_value: float | None = None
    fallback_values_by_key: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        if not self.logical_id or not self.name:
            raise ValueError("Sensor logical ID and EnergyPlus name are required.")
        if self.exchange_kind not in {ExchangeKind.VARIABLE, ExchangeKind.METER}:
            raise ValueError(f"Unsupported exchange kind: {self.exchange_kind}")


@dataclass(frozen=True)
class SensorSettings:
    output_root: Path
    output_directory: Path
    snapshots_jsonl: str
    snapshots_csv: str
    discovery_csv: str
    manifest_json: str
    validation_json: str
    flush_every_snapshots: int
    weather_run_environment_type: int
    minimum_snapshots: int
    expected_zone_count: int
    definitions: tuple[SensorDefinition, ...]
    zones: tuple[str, ...]
    unavailable_configured: tuple[SensorDefinition, ...]


def _definition(raw: dict[str, Any], kind: ExchangeKind, required: bool) -> SensorDefinition:
    return SensorDefinition(
        logical_id=str(raw.get("logical_id", "")),
        display_name=str(raw.get("display_name", "")),
        exchange_kind=kind,
        name=str(raw.get("name", "")),
        key=str(raw.get("key", "")),
        units=str(raw.get("units", "")),
        scope=SensorScope(str(raw.get("scope", ""))),
        required=required,
        minimum=float(raw["minimum"]) if "minimum" in raw else None,
        maximum=float(raw["maximum"]) if "maximum" in raw else None,
        description=str(raw.get("description", "")),
        enabled=bool(raw.get("enabled", True)),
        unavailable_reason=str(raw.get("unavailable_reason", "")),
        fallback_values_by_key=tuple(
            (str(key), float(value)) for key, value in raw.get("fallback_values_by_key", {}).items()
        ),
    )


def expand_zone_definitions(
    definitions: list[SensorDefinition], zones: list[str]
) -> list[SensorDefinition]:
    expanded: list[SensorDefinition] = []
    for definition in definitions:
        if definition.scope is SensorScope.ZONE and definition.enabled:
            expanded.extend(
                SensorDefinition(
                    logical_id=f"{definition.logical_id}.{zone}",
                    display_name=definition.display_name,
                    exchange_kind=definition.exchange_kind,
                    name=definition.name,
                    key=definition.key.replace("{zone}", zone),
                    units=definition.units,
                    scope=definition.scope,
                    required=definition.required,
                    expected_value_type=definition.expected_value_type,
                    minimum=definition.minimum,
                    maximum=definition.maximum,
                    description=definition.description,
                    fallback_value=dict(definition.fallback_values_by_key).get(zone),
                )
                for zone in zones
            )
        elif definition.enabled:
            expanded.append(definition)
    return expanded


def load_sensor_settings(path: Path, root: Path) -> SensorSettings:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Sensor configuration must be a mapping.")
    extraction = raw["sensor_extraction"]
    safety = raw["safety"]
    forbidden = (
        "allow_actuator_handles",
        "allow_actuator_reads",
        "allow_actuator_writes",
        "allow_internal_variable_access",
        "allow_idf_modification",
        "allow_weather_modification",
    )
    if not safety.get("read_only") or any(safety.get(name) for name in forbidden):
        raise ValueError("Module 4 configuration must remain strictly read-only.")
    if extraction["callback"] != "end_zone_timestep_after_zone_reporting":
        raise ValueError("Unsupported sensor callback.")
    manifest = json.loads((root / "models/MODEL_MANIFEST.json").read_text(encoding="utf-8"))
    zones = [str(zone) for zone in manifest["zone_names"]]
    configured: list[SensorDefinition] = []
    for section, kind in (("variables", ExchangeKind.VARIABLE), ("meters", ExchangeKind.METER)):
        for required in (True, False):
            key = "required" if required else "optional"
            configured.extend(_definition(item, kind, required) for item in raw[section][key])
    unavailable = tuple(item for item in configured if not item.enabled)
    definitions = tuple(expand_zone_definitions(configured, zones))
    output_root_raw = Path(str(extraction["output_root"]))
    if output_root_raw.is_absolute():
        raise ValueError("Sensor output root must be repository-relative.")
    output_root = (root / output_root_raw).resolve()
    output = (output_root / "current").resolve()
    output.relative_to(output_root)
    validation = raw["validation"]
    if int(validation["expected_zone_count"]) != len(zones):
        raise ValueError("Configured zone count does not match the model manifest.")
    return SensorSettings(
        output_root=output_root,
        output_directory=output,
        snapshots_jsonl=str(extraction["snapshots_jsonl"]),
        snapshots_csv=str(extraction["snapshots_csv"]),
        discovery_csv=str(extraction["discovery_csv"]),
        manifest_json=str(extraction["manifest_json"]),
        validation_json=str(extraction["validation_json"]),
        flush_every_snapshots=int(extraction["flush_every_snapshots"]),
        weather_run_environment_type=int(extraction["weather_run_environment_type"]),
        minimum_snapshots=int(validation["minimum_snapshots"]),
        expected_zone_count=int(validation["expected_zone_count"]),
        definitions=definitions,
        zones=tuple(zones),
        unavailable_configured=unavailable,
    )
