"""The sole runtime-validated route to physical actuator writes."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from src.control.models import ActuatorIdentity
from src.safety.models import GuardedCommand, GuardOutcome, SafetyReason, validate_guarded_authority


@dataclass(frozen=True)
class WriteAttempt:
    command_id: str | None
    guard_decision_id: str | None
    operation: str
    permitted: bool
    reason: str
    value: float | None


class GuardedCommandBuffer:
    def __init__(self, actuator: ActuatorIdentity, run_id: str, environment_id: str) -> None:
        self.actuator, self.run_id, self.environment_id = actuator, run_id, environment_id
        self._latest: GuardedCommand | None = None
        self._lock = threading.RLock()
        self._ids: set[str] = set()
        self.blocked_bypasses = 0
        self.expired = 0
        self.replaced = 0
        self.shutdown_started = False

    def publish(self, command: object) -> None:
        with self._lock:
            if not isinstance(command, GuardedCommand):
                self.blocked_bypasses += 1
                raise TypeError(SafetyReason.RAW_COMMAND_BYPASS_BLOCKED)
            if not validate_guarded_authority(command):
                self.blocked_bypasses += 1
                raise ValueError("Forged GuardedCommand blocked.")
            if command.run_id != self.run_id or command.environment_id != self.environment_id:
                raise ValueError("GuardedCommand has wrong runtime identity.")
            if command.actuator != self.actuator or not command.guard_decision_id:
                raise ValueError("GuardedCommand lacks approved authority.")
            if command.command_id in self._ids:
                raise ValueError("Duplicate guarded command.")
            if self._latest is not None:
                self.replaced += 1
            self._ids.add(command.command_id)
            self._latest = command

    def latest(self, sequence: int) -> GuardedCommand | None:
        with self._lock:
            if self._latest is not None and sequence > self._latest.expires_after_sequence:
                self._latest = None
                self.expired += 1
            if self._latest is None or sequence < self._latest.valid_from_sequence:
                return None
            return self._latest

    def shutdown(self) -> None:
        with self._lock:
            self.shutdown_started = True
            self._latest = None


class PhysicalWriteGate:
    def __init__(self, actuator: ActuatorIdentity, run_id: str, environment_id: str) -> None:
        self.actuator, self.run_id, self.environment_id = actuator, run_id, environment_id
        self.attempts: list[WriteAttempt] = []

    def submit(
        self, exchange: Any, state: Any, handle: int, command: object, current_sequence: int
    ) -> bool:
        if not isinstance(command, GuardedCommand):
            self.attempts.append(
                WriteAttempt(
                    None, None, "BLOCK", False, SafetyReason.RAW_COMMAND_BYPASS_BLOCKED, None
                )
            )
            return False
        valid = (
            validate_guarded_authority(command)
            and command.run_id == self.run_id
            and command.environment_id == self.environment_id
            and command.actuator == self.actuator
            and bool(command.guard_decision_id)
            and current_sequence <= command.expires_after_sequence
        )
        if not valid:
            self.attempts.append(
                WriteAttempt(
                    command.command_id,
                    command.guard_decision_id,
                    "BLOCK",
                    False,
                    "invalid_guard_authority",
                    None,
                )
            )
            return False
        if command.outcome == GuardOutcome.RESET_TO_NATIVE or command.reset_required:
            exchange.reset_actuator(state, handle)
            self.attempts.append(
                WriteAttempt(
                    command.command_id,
                    command.guard_decision_id,
                    "RESET",
                    True,
                    command.reason,
                    None,
                )
            )
            return True
        if command.applied_value is None:
            self.attempts.append(
                WriteAttempt(
                    command.command_id,
                    command.guard_decision_id,
                    "BLOCK",
                    False,
                    "missing_applied_value",
                    None,
                )
            )
            return False
        exchange.set_actuator_value(state, handle, command.applied_value)
        self.attempts.append(
            WriteAttempt(
                command.command_id,
                command.guard_decision_id,
                "SET",
                True,
                command.reason,
                command.applied_value,
            )
        )
        return True
