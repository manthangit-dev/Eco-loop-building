"""Shared synthetic Module 6 test objects."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from src.state.models import BuildingState, RunCompletion, RunMetadata
from src.state.normalizer import StateNormalizer, snapshot_from_dict
from src.state.zone_classification import load_zone_classification

ROOT = Path(__file__).resolve().parents[1]


def sample_state(run_id: str = "test-run", sequence: int = 1) -> BuildingState:
    source = ROOT / "data/output/module_4_sensor_extraction/current/sensor_snapshots.jsonl"
    with source.open(encoding="utf-8") as stream:
        raw = json.loads(stream.readline())
    raw["sequence"] = sequence
    normalizer = StateNormalizer(
        run_id,
        "test",
        load_zone_classification(ROOT / "config/zone_classification.json"),
    )
    return normalizer.normalize(snapshot_from_dict(raw))


def metadata(run_id: str = "test-run", expected: int = 1) -> RunMetadata:
    return RunMetadata(
        run_id=run_id,
        module=6,
        execution_mode="test",
        status="RUNNING",
        started_at_utc=datetime.now(UTC).isoformat(),
        energyplus_version="26.1",
        api_version="0.2",
        model_path="models/test.idf",
        model_checksum="a" * 64,
        weather_path="weather/test.epw",
        weather_checksum="b" * 64,
        configuration_checksum="c" * 64,
        expected_snapshot_count=expected,
    )


def completion(run_id: str = "test-run", count: int = 1) -> RunCompletion:
    return RunCompletion(
        run_id=run_id,
        status="COMPLETED",
        finished_at_utc=datetime.now(UTC).isoformat(),
        persisted_snapshot_count=count,
        first_sequence=1,
        last_sequence=count,
        first_simulation_timestamp="0.25",
        last_simulation_timestamp=str(count * 0.25),
        severe_count=0,
        fatal_count=0,
        callback_error_count=0,
        api_error_count=0,
        subscriber_error_count=0,
        persistence_error_count=0,
        queue_drained=True,
    )


def with_sequence(state: BuildingState, sequence: int) -> BuildingState:
    return replace(
        state,
        sequence=sequence,
        raw_snapshot_sequence=sequence,
        fingerprint=f"{sequence:064x}",
    )
