"""Streaming, path-contained actuator audit writers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, TextIO

from src.energyplus.actuator_events import EVENT_HEADERS, ActuatorEvent


class ActuatorWriters:
    def __init__(self, output: Path, approved_root: Path, jsonl_name: str, csv_name: str) -> None:
        resolved = output.resolve()
        resolved.relative_to(approved_root.resolve())
        if resolved == approved_root.resolve():
            raise ValueError("Actuator output must be below its approved root.")
        resolved.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = resolved / jsonl_name
        self.csv_path = resolved / csv_name
        self._json: TextIO = self.jsonl_path.with_suffix(".jsonl.tmp").open(
            "w", encoding="utf-8", newline="\n"
        )
        self._csv: TextIO = self.csv_path.with_suffix(".csv.tmp").open(
            "w", encoding="utf-8", newline=""
        )
        self._csv_writer = csv.DictWriter(self._csv, fieldnames=EVENT_HEADERS)
        self._csv_writer.writeheader()
        self.count = 0
        self.closed = False

    def write(self, event: ActuatorEvent) -> None:
        if self.closed:
            raise RuntimeError("Actuator event writer is closed.")
        self._json.write(event.to_json() + "\n")
        self._csv_writer.writerow(event.to_dict())
        self.count += 1
        if self.count % 100 == 0:
            self.flush()

    def flush(self) -> None:
        self._json.flush()
        self._csv.flush()

    def close(self) -> None:
        if self.closed:
            return
        self.flush()
        json_temp = Path(self._json.name)
        csv_temp = Path(self._csv.name)
        self._json.close()
        self._csv.close()
        json_temp.replace(self.jsonl_path)
        csv_temp.replace(self.csv_path)
        self.closed = True


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
