"""Streaming JSONL and flattened CSV writers for sensor snapshots."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TextIO

from src.energyplus.sensor_snapshot import (
    SensorSnapshot,
    csv_headers,
    flatten_snapshot,
)


class SensorWriters:
    def __init__(
        self,
        output_directory: Path,
        approved_root: Path,
        jsonl_name: str,
        csv_name: str,
        zones: tuple[str, ...],
        optional_meter_ids: tuple[str, ...],
        flush_every: int,
    ) -> None:
        output = output_directory.resolve()
        output.relative_to(approved_root.resolve())
        if output == approved_root.resolve():
            raise ValueError("Sensor output must be a child of the approved root.")
        output.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = output / jsonl_name
        self.csv_path = output / csv_name
        self._jsonl_temp = self.jsonl_path.with_suffix(self.jsonl_path.suffix + ".tmp")
        self._csv_temp = self.csv_path.with_suffix(self.csv_path.suffix + ".tmp")
        self._zones = zones
        self._optional_meter_ids = optional_meter_ids
        self._flush_every = flush_every
        self._count = 0
        self._json_stream: TextIO = self._jsonl_temp.open(
            "w", encoding="utf-8", newline="\n"
        )
        self._csv_stream: TextIO = self._csv_temp.open(
            "w", encoding="utf-8", newline=""
        )
        self._headers = csv_headers(zones, optional_meter_ids)
        self._writer = csv.DictWriter(
            self._csv_stream, fieldnames=self._headers, extrasaction="raise"
        )
        self._writer.writeheader()
        self.closed = False

    def write(self, snapshot: SensorSnapshot) -> None:
        if self.closed:
            raise RuntimeError("Sensor writers are closed.")
        self._json_stream.write(snapshot.to_json() + "\n")
        self._writer.writerow(
            flatten_snapshot(snapshot, self._zones, self._optional_meter_ids)
        )
        self._count += 1
        if self._count % self._flush_every == 0:
            self.flush()

    def flush(self) -> None:
        self._json_stream.flush()
        self._csv_stream.flush()

    def close(self) -> None:
        if self.closed:
            return
        self.flush()
        self._json_stream.close()
        self._csv_stream.close()
        self._jsonl_temp.replace(self.jsonl_path)
        self._csv_temp.replace(self.csv_path)
        self.closed = True

    def __enter__(self) -> SensorWriters:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

