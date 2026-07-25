"""Deterministic calendar plan for the bounded Module 5 experiment."""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass
from enum import StrEnum

from src.energyplus.actuator_definitions import ActuatorDefinition, ActuatorSettings


class WindowPosition(StrEnum):
    BEFORE = "before"
    DURING = "during"
    AFTER = "after"


@dataclass(frozen=True)
class ActuatorPlan:
    plan_id: str
    target_zone: str
    actuator: ActuatorDefinition
    month: int
    day: int
    start_minute_of_day: int
    end_minute_of_day: int
    baseline_setpoint: float
    offset: float
    requested_setpoint: float
    approved_setpoint: float
    clamped: bool
    expected_timesteps: int
    reset_required: bool

    def __post_init__(self) -> None:
        if (
            not 1 <= self.month <= 12
            or not 1 <= self.day <= calendar.monthrange(2024, self.month)[1]
        ):
            raise ValueError("Invalid intervention date.")
        if self.end_minute_of_day <= self.start_minute_of_day:
            raise ValueError("Intervention end must be after start.")
        if self.start_minute_of_day % 15 or self.end_minute_of_day % 15:
            raise ValueError("Intervention must align to 15-minute timesteps.")
        if not all(
            math.isfinite(value)
            for value in (self.baseline_setpoint, self.offset, self.approved_setpoint)
        ):
            raise ValueError("Plan temperatures must be finite.")
        if abs(self.offset) > self.actuator.maximum_offset:
            raise ValueError("Requested offset exceeds the configured maximum.")
        if not self.actuator.minimum <= self.approved_setpoint <= self.actuator.maximum:
            raise ValueError("Approved set-point is outside absolute limits.")
        if self.target_zone != self.actuator.target_zone:
            raise ValueError("Plan target does not match the approved actuator.")

    def position(self, month: int, day: int, hour: int, minute: int) -> WindowPosition:
        date_key = (month, day)
        plan_date = (self.month, self.day)
        minute_of_day = hour * 60 + minute
        if date_key < plan_date or (
            date_key == plan_date and minute_of_day < self.start_minute_of_day
        ):
            return WindowPosition.BEFORE
        if date_key == plan_date and minute_of_day < self.end_minute_of_day:
            return WindowPosition.DURING
        return WindowPosition.AFTER


def build_plan(settings: ActuatorSettings) -> ActuatorPlan:
    raw = settings.raw["intervention"]
    baseline = float(raw["baseline_setpoint_celsius"])
    offset = float(raw["offset_celsius"])
    requested = baseline + offset
    approved = min(max(requested, settings.definition.minimum), settings.definition.maximum)
    if abs(approved - baseline) < float(raw["minimum_meaningful_change_celsius"]):
        raise ValueError("Approved change is too small to verify meaningfully.")
    return ActuatorPlan(
        plan_id="module5-fixed-window-v1",
        target_zone=settings.definition.target_zone,
        actuator=settings.definition,
        month=int(raw["month"]),
        day=int(raw["day"]),
        start_minute_of_day=int(raw["start_hour"]) * 60 + int(raw["start_minute"]),
        end_minute_of_day=int(raw["end_hour"]) * 60 + int(raw["end_minute"]),
        baseline_setpoint=baseline,
        offset=offset,
        requested_setpoint=requested,
        approved_setpoint=approved,
        clamped=approved != requested,
        expected_timesteps=int(raw["expected_zone_timesteps"]),
        reset_required=bool(raw["reset_after_window"]),
    )
