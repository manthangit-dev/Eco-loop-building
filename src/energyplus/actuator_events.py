"""Typed audit events for deterministic actuator access."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class ActuatorEventType(StrEnum):
    DISCOVERED = "DISCOVERED"
    HANDLE_ACQUIRED = "HANDLE_ACQUIRED"
    CONTROL_RUN_OBSERVATION = "CONTROL_RUN_OBSERVATION"
    OVERRIDE_APPLIED = "OVERRIDE_APPLIED"
    OVERRIDE_REAPPLIED = "OVERRIDE_REAPPLIED"
    OVERRIDE_RESET = "OVERRIDE_RESET"
    WRITE_REJECTED = "WRITE_REJECTED"
    API_ERROR = "API_ERROR"
    CALLBACK_ERROR = "CALLBACK_ERROR"
    POST_RESET_VERIFIED = "POST_RESET_VERIFIED"


@dataclass(frozen=True)
class ActuatorEvent:
    sequence: int
    simulation_timestamp: str
    event_type: ActuatorEventType
    run_type: str
    zone: str
    component_type: str
    control_type: str
    key: str
    handle: int | None
    baseline_setpoint: float | None
    requested_setpoint: float | None
    approved_setpoint: float | None
    effective_setpoint: float | None
    occupancy: float | None
    api_error: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["event_type"] = self.event_type.value
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)


EVENT_HEADERS = [
    "sequence",
    "simulation_timestamp",
    "event_type",
    "run_type",
    "zone",
    "component_type",
    "control_type",
    "key",
    "handle",
    "baseline_setpoint",
    "requested_setpoint",
    "approved_setpoint",
    "effective_setpoint",
    "occupancy",
    "api_error",
    "reason",
]
