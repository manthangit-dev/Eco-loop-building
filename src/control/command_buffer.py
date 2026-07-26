"""Thread-safe bounded latest-command buffer."""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from typing import Any

from src.control.models import ActuatorIdentity, ControlCommand


@dataclass
class CommandBufferStatistics:
    published: int = 0
    rejected: int = 0
    expired: int = 0
    cleared: int = 0
    replaced: int = 0
    shutdown: bool = False


class LatestCommandBuffer:
    def __init__(self, approved_actuator: ActuatorIdentity) -> None:
        self.approved_actuator = approved_actuator
        self._lock = threading.RLock()
        self._latest: ControlCommand | None = None
        self._ids: set[str] = set()
        self._last_sequence = 0
        self._stats = CommandBufferStatistics()

    def publish(self, command: ControlCommand) -> None:
        with self._lock:
            if self._stats.shutdown:
                raise RuntimeError("Command buffer is shut down.")
            if (
                command.command_id in self._ids
                or command.issued_from_sequence < self._last_sequence
            ):
                self._stats.rejected += 1
                raise ValueError("Duplicate or decreasing command.")
            if command.actuator != self.approved_actuator:
                self._stats.rejected += 1
                raise ValueError("Command actuator is not the single approved actuator.")
            self._ids.add(command.command_id)
            self._last_sequence = command.issued_from_sequence
            if self._latest is not None:
                self._stats.replaced += 1
            self._latest = command
            self._stats.published += 1

    def latest(self, sequence: int) -> ControlCommand | None:
        with self._lock:
            command = self._latest
            if command is not None and sequence > command.expires_after_sequence:
                self._latest = None
                self._stats.expired += 1
                return None
            if command is None or sequence < command.valid_from_sequence:
                return None
            return command

    def clear(self) -> None:
        with self._lock:
            self._latest = None
            self._stats.cleared += 1

    def shutdown(self) -> None:
        with self._lock:
            self._latest = None
            self._stats.shutdown = True

    def statistics(self) -> dict[str, Any]:
        with self._lock:
            return {**asdict(self._stats), "active": self._latest is not None}
