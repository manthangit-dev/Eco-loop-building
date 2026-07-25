"""Bounded, exception-safe EnergyPlus lifecycle callback collection."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class CallbackCollector:
    def __init__(
        self,
        log_path: Path,
        maximum_stored_messages: int,
        maximum_message_length: int,
    ) -> None:
        self.log_path = log_path
        self.maximum_stored_messages = maximum_stored_messages
        self.maximum_message_length = maximum_message_length
        self.progress_events: list[dict[str, str | int]] = []
        self.messages: list[str] = []
        self.message_count = 0
        self.truncated_message_count = 0
        self.environment_start_count = 0
        self.warmup_complete_count = 0
        self.errors: list[str] = []
        self.references: list[Callable[..., None]] = []

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat()

    def _contain(self, name: str, operation: Callable[[], None]) -> None:
        try:
            operation()
        except BaseException as exc:
            self.errors.append(f"{name}: {type(exc).__name__}: {exc}")

    def progress_callback(self) -> Callable[[int], None]:
        def callback(progress: int) -> None:
            def collect() -> None:
                if not 0 <= progress <= 100:
                    raise ValueError(f"Progress outside 0..100: {progress}")
                self.progress_events.append({"timestamp": self._timestamp(), "progress": progress})

            self._contain("progress", collect)

        self.references.append(callback)
        return callback

    def message_callback(self) -> Callable[[bytes], None]:
        def callback(payload: bytes) -> None:
            def collect() -> None:
                text = payload.decode("utf-8", errors="replace").replace("\r\n", "\n")
                text = text.replace("\r", "\n").rstrip("\n")
                self.message_count += 1
                stored = text
                if len(stored) > self.maximum_message_length:
                    stored = stored[: self.maximum_message_length]
                    self.truncated_message_count += 1
                with self.log_path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(f"{self._timestamp()} {stored}\n")
                if len(self.messages) < self.maximum_stored_messages:
                    self.messages.append(stored)

            self._contain("message", collect)

        self.references.append(callback)
        return callback

    def begin_environment_callback(self) -> Callable[[Any], None]:
        def callback(_state: Any) -> None:
            self._contain(
                "begin_environment",
                lambda: setattr(self, "environment_start_count", self.environment_start_count + 1),
            )

        self.references.append(callback)
        return callback

    def warmup_complete_callback(self) -> Callable[[Any], None]:
        def callback(_state: Any) -> None:
            self._contain(
                "warmup_complete",
                lambda: setattr(self, "warmup_complete_count", self.warmup_complete_count + 1),
            )

        self.references.append(callback)
        return callback
