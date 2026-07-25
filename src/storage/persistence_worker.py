"""Bounded queue and dedicated SQLite-owning persistence thread."""

from __future__ import annotations

import queue
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic
from typing import Any

from src.state.models import BuildingState, RunCompletion, RunMetadata
from src.storage.sqlite_store import SQLiteStateStore


@dataclass
class PersistenceStatistics:
    enqueued_count: int = 0
    persisted_count: int = 0
    queue_high_water_mark: int = 0
    batch_count: int = 0
    commit_count: int = 0
    rollback_count: int = 0
    persistence_errors: int = 0
    backpressure_events: int = 0
    maximum_enqueue_delay_seconds: float = 0.0
    worker_healthy: bool = True
    final_drained: bool = False


class StatePersistenceWorker:
    _STOP = object()

    def __init__(
        self,
        database_path: Path,
        approved_root: Path,
        metadata: RunMetadata,
        *,
        queue_capacity: int,
        batch_size: int,
        enqueue_timeout_seconds: float,
        journal_mode: str = "WAL",
        busy_timeout_ms: int = 5000,
    ) -> None:
        if queue_capacity < 1 or batch_size < 1:
            raise ValueError("Persistence queue and batch must be bounded and positive.")
        self.database_path = database_path
        self.approved_root = approved_root
        self.metadata = metadata
        self.batch_size = batch_size
        self.enqueue_timeout_seconds = enqueue_timeout_seconds
        self.journal_mode = journal_mode
        self.busy_timeout_ms = busy_timeout_ms
        self._queue: queue.Queue[BuildingState | object] = queue.Queue(queue_capacity)
        self._stats = PersistenceStatistics()
        self._thread = threading.Thread(target=self._run, name="state-sqlite-writer", daemon=False)
        self._ready = threading.Event()
        self._finished = threading.Event()
        self._completion: RunCompletion | None = None
        self._error: BaseException | None = None
        self._last_enqueued_sequence = 0

    def start(self) -> None:
        self._thread.start()
        if not self._ready.wait(10):
            raise RuntimeError("Persistence worker did not initialize.")
        self.raise_if_failed()

    def enqueue(self, state: BuildingState) -> None:
        self.raise_if_failed()
        if state.sequence <= self._last_enqueued_sequence:
            raise RuntimeError("Out-of-order persistence enqueue.")
        started = monotonic()
        try:
            self._queue.put(state, timeout=self.enqueue_timeout_seconds)
        except queue.Full as exc:
            self._stats.backpressure_events += 1
            raise RuntimeError("Persistence queue backpressure timeout.") from exc
        delay = monotonic() - started
        self._stats.maximum_enqueue_delay_seconds = max(
            self._stats.maximum_enqueue_delay_seconds, delay
        )
        self._last_enqueued_sequence = state.sequence
        self._stats.enqueued_count += 1
        self._stats.queue_high_water_mark = max(
            self._stats.queue_high_water_mark, self._queue.qsize()
        )

    def set_completion(self, completion: RunCompletion) -> None:
        self._completion = completion

    def stop(self, timeout: float = 60.0) -> None:
        self._queue.put(self._STOP, timeout=self.enqueue_timeout_seconds)
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise RuntimeError("Persistence worker did not stop in time.")
        self.raise_if_failed()

    def flush(self, timeout: float = 60.0) -> None:
        started = monotonic()
        while self._queue.unfinished_tasks and monotonic() - started < timeout:
            self.raise_if_failed()
            self._finished.wait(0.01)
        if self._queue.unfinished_tasks:
            raise RuntimeError("Persistence flush timed out.")

    def _run(self) -> None:
        store: SQLiteStateStore | None = None
        try:
            store = SQLiteStateStore(
                self.database_path,
                self.approved_root,
                journal_mode=self.journal_mode,
                busy_timeout_ms=self.busy_timeout_ms,
            )
            store.initialise_schema()
            store.begin_run(self.metadata)
            self._ready.set()
            batch: list[BuildingState] = []
            while True:
                item = self._queue.get()
                if item is self._STOP:
                    self._queue.task_done()
                    if batch:
                        store.append_states(tuple(batch))
                        self._stats.persisted_count += len(batch)
                        self._stats.batch_count += 1
                        batch.clear()
                    break
                if not isinstance(item, BuildingState):
                    raise RuntimeError("Unexpected persistence queue item.")
                batch.append(item)
                self._queue.task_done()
                if len(batch) >= self.batch_size:
                    store.append_states(tuple(batch))
                    self._stats.persisted_count += len(batch)
                    self._stats.batch_count += 1
                    batch.clear()
                self._finished.set()
                self._finished.clear()
            if self._completion is not None:
                completion = self._completion
                completion = RunCompletion(
                    **{
                        **asdict(completion),
                        "persisted_snapshot_count": self._stats.persisted_count,
                        "persistence_error_count": self._stats.persistence_errors,
                        "queue_drained": True,
                    }
                )
                store.finalise_run(completion)
            self._stats.commit_count = store.commit_count
            self._stats.rollback_count = store.rollback_count
            self._stats.final_drained = self._queue.empty()
        except BaseException as exc:
            self._error = exc
            self._stats.persistence_errors += 1
            self._stats.worker_healthy = False
            self._ready.set()
        finally:
            if store is not None:
                store.close()
            self._finished.set()

    def raise_if_failed(self) -> None:
        if self._error is not None:
            raise RuntimeError(f"Persistence worker failed: {self._error}") from self._error

    def statistics(self) -> dict[str, Any]:
        return asdict(self._stats)
