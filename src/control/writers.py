"""Bounded dedicated controller persistence worker."""

from __future__ import annotations

import queue
import threading
from pathlib import Path

from src.control.models import ControlCommand, ControlDecision, ControllerRunMetadata
from src.storage.controller_store import ControllerStore


class ControllerWriter:
    _STOP = object()

    def __init__(
        self, database: Path, root: Path, metadata: ControllerRunMetadata, capacity: int = 512
    ) -> None:
        self.database = database
        self.root = root
        self.metadata = metadata
        self.queue: queue.Queue[tuple[ControlDecision, ControlCommand | None] | object] = (
            queue.Queue(capacity)
        )
        self.persisted_decisions = 0
        self.persisted_commands = 0
        self.error: BaseException | None = None
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run, name="controller-sqlite-writer")

    def start(self) -> None:
        self.thread.start()
        if not self.ready.wait(10):
            raise RuntimeError("Controller writer did not start.")
        self.raise_if_failed()

    def enqueue(self, decision: ControlDecision, command: ControlCommand | None) -> None:
        self.raise_if_failed()
        self.queue.put((decision, command), timeout=5)

    def stop(self) -> None:
        self.queue.put(self._STOP, timeout=5)
        self.thread.join(60)
        if self.thread.is_alive():
            raise RuntimeError("Controller writer did not drain.")
        self.raise_if_failed()

    def _run(self) -> None:
        store: ControllerStore | None = None
        try:
            store = ControllerStore(self.database, self.root)
            store.begin_run(self.metadata)
            self.ready.set()
            batch: list[tuple[ControlDecision, ControlCommand | None]] = []
            while True:
                item = self.queue.get()
                try:
                    if item is self._STOP:
                        if batch:
                            store.append_batch(batch)
                            self.persisted_decisions += len(batch)
                            self.persisted_commands += sum(
                                command is not None for _, command in batch
                            )
                        break
                    if not isinstance(item, tuple):
                        raise TypeError("Unexpected controller writer item.")
                    decision, command = item
                    batch.append((decision, command))
                    if len(batch) >= 100:
                        store.append_batch(batch)
                        self.persisted_decisions += len(batch)
                        self.persisted_commands += sum(command is not None for _, command in batch)
                        batch.clear()
                finally:
                    self.queue.task_done()
        except BaseException as exc:
            self.error = exc
            self.ready.set()
        finally:
            if store is not None:
                store.close()

    def raise_if_failed(self) -> None:
        if self.error is not None:
            raise RuntimeError(f"Controller persistence failed: {self.error}") from self.error
