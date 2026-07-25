"""Validated Module 6 configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


@dataclass(frozen=True)
class StateSettings:
    root: Path
    output_root: Path
    replay_output: Path
    live_output: Path
    database_name: str
    schema_version: int
    history_capacity: int
    queue_capacity: int
    batch_size: int
    enqueue_timeout_seconds: float
    journal_mode: str
    busy_timeout_ms: int
    expected_snapshot_count: int
    expected_zone_count: int
    raw: dict[str, Any]

    def database_path(self, mode: str) -> Path:
        output = self.replay_output if mode == "replay" else self.live_output
        return output / self.database_name


def load_state_settings(path: Path, root: Path) -> StateSettings:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    safety = raw["safety"]
    if any(bool(value) for key, value in safety.items() if key.startswith("allow_")):
        raise ValueError("Module 6 safety configuration must deny all unsafe capabilities.")
    execution = raw["execution"]
    storage = raw["storage"]
    bus = raw["state_bus"]
    output_raw = Path(str(execution["output_root"]))
    if output_raw.is_absolute():
        raise ValueError("State output root must be repository-relative.")
    output_root = (root / output_raw).resolve()
    replay = (output_root / str(execution["replay_output_directory"])).resolve()
    live = (output_root / str(execution["live_output_directory"])).resolve()
    replay.relative_to(output_root)
    live.relative_to(output_root)
    if int(raw["state_model"]["schema_version"]) != 1 or int(storage["schema_version"]) != 1:
        raise ValueError("Only canonical/storage schema version 1 is supported.")
    history = int(bus["history_capacity"])
    queue_capacity = int(storage["persistence_queue_capacity"])
    if history < 1 or queue_capacity < 1:
        raise ValueError("State history and persistence queue must be bounded.")
    return StateSettings(
        root=root,
        output_root=output_root,
        replay_output=replay,
        live_output=live,
        database_name=str(storage["database_name"]),
        schema_version=1,
        history_capacity=history,
        queue_capacity=queue_capacity,
        batch_size=int(storage["batch_size"]),
        enqueue_timeout_seconds=float(storage["enqueue_timeout_seconds"]),
        journal_mode=str(storage["journal_mode"]),
        busy_timeout_ms=int(storage["busy_timeout_ms"]),
        expected_snapshot_count=int(execution["expected_snapshot_count"]),
        expected_zone_count=int(execution["expected_zone_count"]),
        raw=raw,
    )
