"""Exact-match registry exposing only the approved Module 5 actuator."""

from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.energyplus.actuator_definitions import ActuatorDefinition


@dataclass(frozen=True)
class ActuatorDiscovery:
    what: str
    component_type: str
    control_type: str
    unique_key: str
    units: str
    source: str
    occupied_zone: bool
    zone_count: int
    eligible: bool
    rejection_reason: str


class ActuatorRegistry:
    def __init__(self, approved: ActuatorDefinition, occupied_zones: tuple[str, ...]) -> None:
        self.approved = approved
        self.occupied_zones = occupied_zones
        self.discoveries: list[ActuatorDiscovery] = []
        self.handle: int | None = None
        self.initialized = False
        self.acquisition_attempts = 0
        self.api_error_count = 0

    def discover(self, exchange: Any, state: Any) -> None:
        if self.discoveries:
            return
        text = exchange.list_available_api_data_csv(state).decode("utf-8-sig")
        for line in text.splitlines()[1:]:
            if line.startswith("**"):
                break
            if not line:
                continue
            row = next(csv.reader(io.StringIO(line)))
            if len(row) < 5 or row[0] != "Actuator":
                continue
            component, control, key, units = row[1:5]
            direct = component == "Zone Temperature Control"
            cooling = control == "Cooling Setpoint"
            occupied = key in self.occupied_zones
            eligible = direct and cooling and occupied and not key.upper().startswith("PLENUM")
            reason = "" if eligible else "Not an isolated occupied-zone cooling set-point."
            self.discoveries.append(
                ActuatorDiscovery(
                    "Actuator",
                    component,
                    control,
                    key,
                    units,
                    "Runtime API CSV",
                    occupied,
                    1 if direct and key else 0,
                    eligible,
                    reason,
                )
            )

    def initialize(self, exchange: Any, state: Any) -> bool:
        if self.initialized:
            return self.handle is not None
        if not exchange.api_data_fully_ready(state):
            return False
        self.discover(exchange, state)
        matches = [
            item
            for item in self.discoveries
            if item.component_type == self.approved.component_type
            and item.control_type == self.approved.control_type
            and item.unique_key == self.approved.unique_key
            and item.eligible
        ]
        if len(matches) != 1:
            self.initialized = True
            return False
        self.acquisition_attempts += 1
        exchange.reset_api_error_flag(state)
        handle = int(
            exchange.get_actuator_handle(
                state,
                self.approved.component_type,
                self.approved.control_type,
                self.approved.unique_key,
            )
        )
        if exchange.api_error_flag(state):
            self.api_error_count += 1
            exchange.reset_api_error_flag(state)
        self.handle = handle if handle != -1 else None
        self.initialized = True
        return self.handle is not None

    def approved_handle(self) -> int:
        if self.handle is None:
            raise RuntimeError("Approved actuator handle is unavailable.")
        return self.handle

    def write_discovery(self, path: Path) -> None:
        headers = (
            list(asdict(self.discoveries[0]))
            if self.discoveries
            else [
                "what",
                "component_type",
                "control_type",
                "unique_key",
                "units",
                "source",
                "occupied_zone",
                "zone_count",
                "eligible",
                "rejection_reason",
            ]
        )
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=headers)
            writer.writeheader()
            writer.writerows(asdict(item) for item in self.discoveries)
