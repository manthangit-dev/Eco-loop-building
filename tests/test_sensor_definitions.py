from dataclasses import replace
from pathlib import Path

import pytest
from src.energyplus.sensor_definitions import (
    ExchangeKind,
    SensorDefinition,
    SensorScope,
    expand_zone_definitions,
    load_sensor_settings,
)

ROOT = Path(__file__).resolve().parents[1]


def definition(**overrides: object) -> SensorDefinition:
    base = SensorDefinition(
        "temperature",
        "Temperature",
        ExchangeKind.VARIABLE,
        "Zone Mean Air Temperature",
        "{zone}",
        "C",
        SensorScope.ZONE,
        True,
    )
    return replace(base, **overrides)


def test_module_4_config_expands_every_manifest_zone() -> None:
    settings = load_sensor_settings(ROOT / "config/sensors.yaml", ROOT)
    temperatures = [
        item
        for item in settings.definitions
        if item.logical_id.startswith("zone_mean_air_temperature.")
    ]
    assert len(settings.zones) == settings.expected_zone_count == 6
    assert {item.key for item in temperatures} == set(settings.zones)
    assert all(item.exchange_kind in {ExchangeKind.VARIABLE, ExchangeKind.METER}
               for item in settings.definitions)
    assert {item.logical_id for item in settings.unavailable_configured} == {
        "zone_fanger_pmv",
        "zone_co2",
    }


def test_definition_rejects_missing_identity_and_non_read_only_kind() -> None:
    with pytest.raises(ValueError, match="required"):
        definition(logical_id="")
    with pytest.raises(ValueError, match="Unsupported"):
        definition(exchange_kind=ExchangeKind.SIMULATION_TIME)


def test_disabled_zone_definition_is_not_expanded() -> None:
    assert expand_zone_definitions([definition(enabled=False)], ["A", "B"]) == []
