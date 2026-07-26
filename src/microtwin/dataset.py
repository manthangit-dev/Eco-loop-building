"""Causally aligned t -> t+1 dataset construction."""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from src.microtwin.config import MicroTwinSettings
from src.planning.provenance import planning_fingerprint


@dataclass(frozen=True)
class Record:
    sequence: int
    timestamp: str
    features: tuple[float, ...]
    temperature_target: float
    demand_target: float
    occupied: bool


def build_dataset(settings: MicroTwinSettings, database: Path) -> tuple[Record, ...]:
    c = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    rows = c.execute(
        """SELECT b.sequence,b.environment_number,b.month,b.day,b.hour,b.minute,b.warmup,
    b.outdoor_dry_bulb_c,b.hvac_electricity_raw_j,z.mean_air_temperature_c,
    z.effective_cooling_setpoint_c,z.occupant_count FROM building_states b JOIN zone_states z
    ON z.building_state_id=b.id WHERE z.exact_name=? ORDER BY b.sequence""",
        (settings.target_zone,),
    ).fetchall()
    c.close()
    result = []
    for index in range(1, len(rows) - 1):
        previous, current, following = rows[index - 1], rows[index], rows[index + 1]
        if (
            current[6]
            or previous[1] != current[1]
            or following[1] != current[1]
            or current[0] != previous[0] + 1
            or following[0] != current[0] + 1
        ):
            continue
        hour = float(current[4]) + float(current[5]) / 60
        features = (
            float(current[9]),
            float(current[9]) - float(previous[9]),
            float(current[7]),
            float(current[7]) - float(previous[7]),
            float(current[10]),
            float(current[10]) - float(previous[10]),
            float(current[11]),
            float(current[8]),
            float(current[8]) - float(previous[8]),
            math.sin(2 * math.pi * hour / 24),
            math.cos(2 * math.pi * hour / 24),
        )
        values = features + (float(following[9]), float(following[8]))
        if not all(math.isfinite(value) for value in values):
            raise ValueError("non-finite telemetry")
        result.append(
            Record(
                int(current[0]),
                f"{current[2]:02}-{current[3]:02} {current[4]:02}:{current[5]:02}",
                features,
                float(following[9]),
                float(following[8]),
                float(current[11]) > 0,
            )
        )
    return tuple(result)


def split(
    records: tuple[Record, ...], settings: MicroTwinSettings
) -> tuple[tuple[Record, ...], tuple[Record, ...], tuple[Record, ...], str]:
    a = int(len(records) * settings.train_fraction)
    b = a + int(len(records) * settings.validation_fraction)
    train, validation, test = records[:a], records[a:b], records[b:]
    return (
        train,
        validation,
        test,
        planning_fingerprint(
            {
                "train": (train[0].sequence, train[-1].sequence),
                "validation": (validation[0].sequence, validation[-1].sequence),
                "test": (test[0].sequence, test[-1].sequence),
            }
        ),
    )
