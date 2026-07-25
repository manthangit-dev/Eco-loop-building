"""Deterministic zone classification loaded from tracked evidence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from src.state.models import DuplicateZoneError, ZoneClassification


@dataclass(frozen=True)
class ZoneEvidence:
    exact_name: str
    zone_id: str
    classification: ZoneClassification
    occupancy_capable: bool
    is_plenum: bool
    evidence: str


def normalise_zone_id(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not value:
        raise ValueError("Zone name cannot normalize to an empty ID.")
    return value


def load_zone_classification(path: Path) -> tuple[ZoneEvidence, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    zones = tuple(
        ZoneEvidence(
            exact_name=str(item["exact_name"]),
            zone_id=str(item["zone_id"]),
            classification=ZoneClassification(str(item["classification"])),
            occupancy_capable=bool(item["occupancy_capable"]),
            is_plenum=bool(item["is_plenum"]),
            evidence=str(item["evidence"]),
        )
        for item in raw["zones"]
    )
    ids = [item.zone_id for item in zones]
    if len(ids) != len(set(ids)):
        raise DuplicateZoneError("Duplicate normalized IDs in zone manifest.")
    for item in zones:
        if item.zone_id != normalise_zone_id(item.exact_name):
            raise ValueError(f"Unstable zone ID for {item.exact_name}.")
    return zones
