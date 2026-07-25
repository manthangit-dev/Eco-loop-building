"""Structured result from a single EnergyPlus Runtime API execution."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class RunStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass
class RunResult:
    run_id: str
    status: RunStatus
    execution_mode: str
    started_at: str
    finished_at: str
    elapsed_seconds: float
    timed_out: bool
    cancelled: bool
    exit_code: int | None
    energyplus_version: str
    api_version: str
    api_library_path: str
    model_path: str
    model_sha256: str
    weather_path: str
    weather_sha256: str
    output_directory: str
    command_line_arguments: list[str]
    progress_events: list[dict[str, Any]] = field(default_factory=list)
    message_count: int = 0
    stored_message_count: int = 0
    truncated_message_count: int = 0
    environment_start_count: int = 0
    warmup_complete_count: int = 0
    callback_errors: list[str] = field(default_factory=list)
    callbacks_cleared: bool = False
    state_deleted: bool = False
    validation_status: str = "NOT_RUN"
    validation_summary_path: str = ""
    comparison_status: str = "NOT_RUN"
    error_message: str = ""
    installation_generated_files_before: list[str] = field(default_factory=list)
    installation_generated_files_after: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
