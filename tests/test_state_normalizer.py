import json
from typing import cast

import pytest
from src.state.models import MissingRequiredZoneError, NonMonotonicSequenceError
from src.state.normalizer import StateNormalizer, snapshot_from_dict
from src.state.zone_classification import load_zone_classification

from tests.state_helpers import ROOT


def _raw() -> dict[str, object]:
    source = ROOT / "data/output/module_4_sensor_extraction/current/sensor_snapshots.jsonl"
    with source.open(encoding="utf-8") as stream:
        return cast(dict[str, object], json.loads(stream.readline()))


def _normalizer() -> StateNormalizer:
    return StateNormalizer(
        "run",
        "replay",
        load_zone_classification(ROOT / "config/zone_classification.json"),
    )


def test_normalizer_preserves_zones_nulls_and_order() -> None:
    state = _normalizer().normalize(snapshot_from_dict(_raw()))
    assert [zone.exact_name for zone in state.zones] == [
        "PLENUM-1",
        "SPACE1-1",
        "SPACE2-1",
        "SPACE3-1",
        "SPACE4-1",
        "SPACE5-1",
    ]
    assert all(zone.pmv is None and zone.co2_ppm is None for zone in state.zones)


def test_normalizer_rejects_missing_zone_and_repeated_sequence() -> None:
    raw = _raw()
    raw["zones"] = raw["zones"][:-1]  # type: ignore[index]
    with pytest.raises(MissingRequiredZoneError):
        _normalizer().normalize(snapshot_from_dict(raw))
    normalizer = _normalizer()
    snapshot = snapshot_from_dict(_raw())
    normalizer.normalize(snapshot)
    with pytest.raises(NonMonotonicSequenceError):
        normalizer.normalize(snapshot)
