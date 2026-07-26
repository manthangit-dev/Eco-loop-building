"""Validated Module 7 configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from src.control.models import ActuatorIdentity


@dataclass(frozen=True)
class FallbackSettings:
    root: Path
    raw: dict[str, Any]
    approved_zones: tuple[str, ...]
    real_zone: str
    actuator: ActuatorIdentity
    minimum_setpoint: float
    maximum_setpoint: float
    maximum_delta: float
    preferred_setpoint: float
    recovery_setpoint: float
    hot_threshold: float
    hysteresis: float
    minimum_hold: int
    occupancy_grace: int
    relaxed_offset: float
    maximum_relaxed: float
    protection_threshold: float
    command_ttl: int
    maximum_sequence_gap: int
    output_root: Path

    def output(self, mode: str) -> Path:
        execution = self.raw["execution"]
        key = {
            "live_shadow": "live_shadow_directory",
            "live_control": "live_control_directory",
        }.get(mode)
        if key is None:
            raise ValueError(f"Mode has no fixed output: {mode}")
        path = (self.output_root / str(execution[key])).resolve()
        path.relative_to(self.output_root)
        return path


def load_fallback_settings(path: Path, root: Path) -> FallbackSettings:
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    controller = raw["controller"]
    boundary = raw["safety_boundary"]
    targets = raw["targets"]
    actuation = raw["actuation"]
    if controller["controller_type"] != "deterministic_rule_based_fallback":
        raise ValueError("Unsupported fallback controller type.")
    if int(controller["schema_version"]) != 1 or int(boundary["final_safety_guard_module"]) != 8:
        raise ValueError("Module 7/schema boundary mismatch.")
    if bool(boundary["final_safety_guard_implemented"]) or any(
        bool(boundary[key]) for key in boundary if key.startswith("allow_")
    ):
        raise ValueError("Module 7 safety boundary must fail closed.")
    if (
        int(controller["real_actuation_maximum_zones"]) != 1
        or int(actuation["maximum_actuators"]) != 1
    ):
        raise ValueError("Module 7 permits exactly one real actuator.")
    output_raw = Path(str(raw["execution"]["output_root"]))
    if output_raw.is_absolute():
        raise ValueError("Output must be repository-relative.")
    output_root = (root / output_raw).resolve()
    occupied = raw["occupied_policy"]
    unoccupied = raw["unoccupied_policy"]
    return FallbackSettings(
        root=root,
        raw=raw,
        approved_zones=tuple(str(item) for item in targets["approved_zone_names"]),
        real_zone=str(targets["real_actuation_zone"]),
        actuator=ActuatorIdentity(
            str(targets["approved_component_type"]),
            str(targets["approved_control_type"]),
            str(targets["approved_unique_key"]),
            str(targets["approved_units"]),
        ),
        minimum_setpoint=float(occupied["minimum_setpoint_celsius"]),
        maximum_setpoint=float(occupied["maximum_setpoint_celsius"]),
        maximum_delta=float(occupied["maximum_delta_from_baseline_celsius"]),
        preferred_setpoint=float(occupied["preferred_setpoint_celsius"]),
        recovery_setpoint=float(occupied["recovery_setpoint_celsius"]),
        hot_threshold=float(occupied["hot_temperature_threshold_celsius"]),
        hysteresis=float(occupied["hysteresis_celsius"]),
        minimum_hold=int(occupied["minimum_hold_zone_timesteps"]),
        occupancy_grace=int(unoccupied["grace_zone_timesteps"]),
        relaxed_offset=float(unoccupied["relaxed_offset_celsius"]),
        maximum_relaxed=float(unoccupied["maximum_relaxed_setpoint_celsius"]),
        protection_threshold=float(unoccupied["temperature_protection_threshold_celsius"]),
        command_ttl=int(raw["staleness"]["command_ttl_zone_timesteps"]),
        maximum_sequence_gap=int(raw["staleness"]["maximum_sequence_gap"]),
        output_root=output_root,
    )
