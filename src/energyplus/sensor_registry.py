"""Read-only EnergyPlus variable and meter handle registry."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.energyplus.sensor_definitions import (
    ExchangeKind,
    SensorDefinition,
    SensorSettings,
)


@dataclass(frozen=True)
class HandleDiscovery:
    logical_id: str
    exchange_kind: str
    name: str
    key: str
    units: str
    required: bool
    handle: int | None
    available: bool
    verification_sources: tuple[str, ...]
    reason: str = ""


class SensorRegistry:
    def __init__(self, settings: SensorSettings, output_directory: Path) -> None:
        self.settings = settings
        self.output_directory = output_directory
        self._handles: dict[str, int] = {}
        self._fallbacks: dict[str, float] = {}
        self.discoveries: list[HandleDiscovery] = []
        self.initialized = False
        self.required_ready = False
        self.api_error_count = 0
        self.discovery_errors: list[str] = []
        self.available_data_captured = False

    def request_variables(self, exchange: Any, state: Any) -> None:
        for definition in self.settings.definitions:
            if definition.exchange_kind is ExchangeKind.VARIABLE:
                exchange.request_variable(state, definition.name, definition.key)

    def _handle(self, exchange: Any, state: Any, definition: SensorDefinition) -> int:
        exchange.reset_api_error_flag(state)
        if definition.exchange_kind is ExchangeKind.VARIABLE:
            handle = int(
                exchange.get_variable_handle(state, definition.name, definition.key)
            )
        else:
            handle = int(exchange.get_meter_handle(state, definition.name))
        if exchange.api_error_flag(state):
            self.api_error_count += 1
            exchange.reset_api_error_flag(state)
        return handle

    def initialize(self, exchange: Any, state: Any) -> bool:
        if self.initialized:
            return self.required_ready
        if not exchange.api_data_fully_ready(state):
            return False
        required_failures = 0
        for definition in self.settings.definitions:
            handle = self._handle(exchange, state, definition)
            available = handle != -1
            if available:
                self._handles[definition.logical_id] = handle
            elif definition.fallback_value is not None:
                self._fallbacks[definition.logical_id] = definition.fallback_value
            elif definition.required:
                required_failures += 1
                self.discovery_errors.append(
                    f"Required handle unavailable: {definition.logical_id}"
                )
            sources = (
                ("Runtime API listing", "RDD")
                if definition.exchange_kind is ExchangeKind.VARIABLE
                else ("Runtime API listing", "MDD")
            )
            self.discoveries.append(
                HandleDiscovery(
                    logical_id=definition.logical_id,
                    exchange_kind=definition.exchange_kind.value,
                    name=definition.name,
                    key=definition.key,
                    units=definition.units,
                    required=definition.required,
                    handle=handle if available else None,
                    available=available,
                    verification_sources=sources,
                    reason=(
                        ""
                        if available
                        else (
                            f"EnergyPlus returned handle -1; verified deterministic "
                            f"fallback {definition.fallback_value} is used."
                            if definition.fallback_value is not None
                            else "EnergyPlus returned handle -1."
                        )
                    ),
                )
            )
        self.initialized = True
        self.required_ready = required_failures == 0
        return self.required_ready

    def capture_available_data(self, exchange: Any, state: Any) -> None:
        if self.available_data_captured:
            return
        payload = exchange.list_available_api_data_csv(state)
        (self.output_directory / self.settings.discovery_csv).write_bytes(payload)
        self.available_data_captured = True

    def handle_for(self, logical_id: str) -> int | None:
        return self._handles.get(logical_id)

    def read(self, exchange: Any, state: Any, logical_id: str) -> float | None:
        if not self.initialized or not self.required_ready:
            raise RuntimeError("Required sensor handles are not ready.")
        handle = self._handles.get(logical_id)
        if handle is None:
            return self._fallbacks.get(logical_id)
        definition = next(
            item for item in self.settings.definitions if item.logical_id == logical_id
        )
        exchange.reset_api_error_flag(state)
        if definition.exchange_kind is ExchangeKind.VARIABLE:
            value = float(exchange.get_variable_value(state, handle))
        else:
            value = float(exchange.get_meter_value(state, handle))
        if exchange.api_error_flag(state):
            self.api_error_count += 1
            exchange.reset_api_error_flag(state)
            raise RuntimeError(f"EnergyPlus API error reading {logical_id}.")
        return value

    def write_manifest(self) -> Path:
        path = self.output_directory / self.settings.manifest_json
        unavailable_configured = [
            {
                "logical_id": item.logical_id,
                "name": item.name,
                "reason": item.unavailable_reason,
            }
            for item in self.settings.unavailable_configured
        ]
        payload = {
            "read_only": True,
            "actuator_access_count": 0,
            "required_handles_ready": self.required_ready,
            "deterministic_fallbacks": self._fallbacks,
            "api_error_count": self.api_error_count,
            "discoveries": [asdict(item) for item in self.discoveries],
            "configured_unavailable_optional": unavailable_configured,
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path
