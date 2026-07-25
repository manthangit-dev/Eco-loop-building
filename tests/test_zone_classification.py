import json
from pathlib import Path

import pytest
from src.state.models import DuplicateZoneError, ZoneClassification
from src.state.zone_classification import load_zone_classification, normalise_zone_id

from tests.state_helpers import ROOT


def test_tracked_zone_classification_has_all_model_zones() -> None:
    zones = load_zone_classification(ROOT / "config/zone_classification.json")
    assert len(zones) == 6
    assert zones[0].classification is ZoneClassification.PLENUM
    assert sum(zone.occupancy_capable for zone in zones) == 5
    assert normalise_zone_id("SPACE1-1") == "space1_1"


def test_duplicate_zone_ids_are_rejected(tmp_path: Path) -> None:
    payload = {
        "zones": [
            {
                "exact_name": "A",
                "zone_id": "a",
                "classification": "OTHER",
                "occupancy_capable": False,
                "is_plenum": False,
                "evidence": "test",
            },
            {
                "exact_name": "A",
                "zone_id": "a",
                "classification": "OTHER",
                "occupancy_capable": False,
                "is_plenum": False,
                "evidence": "test",
            },
        ]
    }
    path = tmp_path / "zones.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(DuplicateZoneError):
        load_zone_classification(path)
