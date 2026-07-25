"""Bounded thread-safe in-process canonical state bus."""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from src.state.models import BuildingState, NonMonotonicSequenceError


@dataclass
class StateBusStatistics:
    published_state_count: int = 0
    rejected_state_count: int = 0
    duplicate_sequence_count: int = 0
    sequence_gap_count: int = 0
    subscriber_notification_count: int = 0
    subscriber_error_count: int = 0
    waiter_count: int = 0
    evicted_state_count: int = 0
    latest_sequence: int = 0
    shutdown: bool = False


class StateBus:
    def __init__(self, history_capacity: int) -> None:
        if history_capacity < 1:
            raise ValueError("StateBus history capacity must be bounded and positive.")
        self.history_capacity = history_capacity
        self._history: deque[BuildingState] = deque(maxlen=history_capacity)
        self._condition = threading.Condition(threading.RLock())
        self._subscribers: dict[int, Callable[[BuildingState], None]] = {}
        self._next_subscriber_id = 1
        self._stats = StateBusStatistics()
        self.subscriber_errors: list[str] = []

    def publish(self, state: BuildingState) -> None:
        with self._condition:
            if self._stats.shutdown:
                self._stats.rejected_state_count += 1
                raise RuntimeError("Cannot publish after StateBus shutdown.")
            latest = self._stats.latest_sequence
            if state.sequence == latest:
                self._stats.duplicate_sequence_count += 1
                self._stats.rejected_state_count += 1
                raise NonMonotonicSequenceError("Duplicate state sequence.")
            if latest and state.sequence < latest:
                self._stats.rejected_state_count += 1
                raise NonMonotonicSequenceError("Decreasing state sequence.")
            if latest and state.sequence > latest + 1:
                self._stats.sequence_gap_count += 1
            if len(self._history) == self.history_capacity:
                self._stats.evicted_state_count += 1
            self._history.append(state)
            self._stats.published_state_count += 1
            self._stats.latest_sequence = state.sequence
            subscribers = tuple(self._subscribers.values())
            self._condition.notify_all()
        for subscriber in subscribers:
            try:
                subscriber(state)
                with self._condition:
                    self._stats.subscriber_notification_count += 1
            except BaseException as exc:
                with self._condition:
                    self._stats.subscriber_error_count += 1
                    self.subscriber_errors.append(f"{type(exc).__name__}: {exc}")

    def latest(self) -> BuildingState | None:
        with self._condition:
            return self._history[-1] if self._history else None

    def recent(self, limit: int) -> tuple[BuildingState, ...]:
        if limit < 0:
            raise ValueError("History limit cannot be negative.")
        with self._condition:
            return tuple(self._history)[-limit:] if limit else ()

    def sequence_range(self, start: int, end: int) -> tuple[BuildingState, ...]:
        with self._condition:
            return tuple(state for state in self._history if start <= state.sequence <= end)

    def wait_for_newer(self, sequence: int, timeout: float | None = None) -> BuildingState | None:
        with self._condition:
            self._stats.waiter_count += 1
            try:
                ready = self._condition.wait_for(
                    lambda: self._stats.latest_sequence > sequence or self._stats.shutdown,
                    timeout,
                )
                if not ready or self._stats.latest_sequence <= sequence:
                    return None
                return self._history[-1]
            finally:
                self._stats.waiter_count -= 1

    def subscribe(self, callback: Callable[[BuildingState], None]) -> int:
        with self._condition:
            identifier = self._next_subscriber_id
            self._next_subscriber_id += 1
            self._subscribers[identifier] = callback
            return identifier

    def unsubscribe(self, identifier: int) -> bool:
        with self._condition:
            return self._subscribers.pop(identifier, None) is not None

    def shutdown(self) -> None:
        with self._condition:
            self._stats.shutdown = True
            self._condition.notify_all()

    def statistics(self) -> dict[str, Any]:
        with self._condition:
            return {
                **asdict(self._stats),
                "current_history_size": len(self._history),
                "subscriber_count": len(self._subscribers),
            }
