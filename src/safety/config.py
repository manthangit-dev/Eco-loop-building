"""Validated Module 8 configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.control.models import ActuatorIdentity


@dataclass(frozen=True)
class SafetySettings:
    root: Path
    raw: dict[str, Any]
    schema_version: int
    enabled: bool
    fail_closed: bool
    actuator: ActuatorIdentity
    zone: str
    approved_zones: tuple[str, ...]
    plenum_zones: tuple[str, ...]
    permitted_environments: tuple[int, ...]
    command_ttl: int
    maximum_state_age: int
    last_safe_ttl: int
    minimum: float
    maximum: float
    maximum_step: float
    maximum_step_per_timestep: float
    marginal_clamp: float


def load_safety_settings(path: Path, root: Path | None = None) -> SafetySettings:
    resolved_root = path.resolve().parents[1] if root is None else root.resolve()
    raw_obj = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw_obj, dict):
        raise ValueError("Safety configuration must be a mapping.")
    raw: dict[str, Any] = raw_obj
    safety = _mapping(raw, "safety")
    approved = _mapping(raw, "approved_actuator")
    runtime = _mapping(raw, "runtime")
    limits = _mapping(raw, "limits")
    version = _integer(safety, "schema_version")
    if version != 1:
        raise ValueError(f"Unsupported safety schema version {version}.")
    zones = _strings(raw, "approved_zones")
    if len(set(zones)) != len(zones):
        raise ValueError("Duplicate approved zone.")
    minimum, maximum = float(limits["minimum_celsius"]), float(limits["maximum_celsius"])
    if minimum >= maximum:
        raise ValueError("Safety minimum must be lower than maximum.")
    ttl = _integer(runtime, "command_ttl_zone_timesteps")
    if ttl < 0:
        raise ValueError("Command TTL cannot be negative.")
    actuator = ActuatorIdentity(
        str(approved["component_type"]),
        str(approved["control_type"]),
        str(approved["actuator_key"]),
        str(approved["units"]),
    )
    zone = str(approved["zone"])
    if zone not in zones:
        raise ValueError("Approved actuator zone is not allowlisted.")
    return SafetySettings(
        resolved_root,
        raw,
        version,
        bool(safety["enabled"]),
        bool(safety["fail_closed"]),
        actuator,
        zone,
        zones,
        _strings(raw, "plenum_zones"),
        tuple(int(value) for value in runtime["permitted_environment_types"]),
        ttl,
        _integer(runtime, "maximum_state_age_zone_timesteps"),
        _integer(runtime, "last_safe_ttl_zone_timesteps"),
        minimum,
        maximum,
        float(limits["maximum_change_per_decision_celsius"]),
        float(limits["maximum_change_per_zone_timestep_celsius"]),
        float(limits["marginal_clamp_celsius"]),
    )


def _mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Missing mapping: {key}.")
    return value


def _integer(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if type(value) is not int:
        raise ValueError(f"{key} must be an integer.")
    return value


def _strings(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a string list.")
    return tuple(value)
