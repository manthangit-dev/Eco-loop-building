from pathlib import Path
from types import SimpleNamespace
from typing import Any

from src.energyplus.sensor_collector import SensorCollector
from src.energyplus.sensor_definitions import (
    ExchangeKind,
    SensorDefinition,
    SensorScope,
    SensorSettings,
)


class Registry:
    initialized = False
    required_ready = False
    api_error_count = 0
    discoveries: list[object] = []

    def request_variables(self, _exchange: object, _state: object) -> None:
        pass

    def initialize(self, _exchange: object, _state: object) -> bool:
        self.initialized = True
        self.required_ready = True
        return True

    def capture_available_data(self, _exchange: object, _state: object) -> None:
        pass

    def read(self, _exchange: object, _state: object, _logical_id: str) -> float:
        return 1.0

    def handle_for(self, _logical_id: str) -> int:
        return 1


class Writer:
    def __init__(self) -> None:
        self.rows: list[object] = []

    def write(self, snapshot: object) -> None:
        self.rows.append(snapshot)


class Exchange:
    ready = True
    warmup = False
    environment_type = 3

    def api_data_fully_ready(self, _state: object) -> bool:
        return self.ready

    def warmup_flag(self, _state: object) -> bool:
        return self.warmup

    def kind_of_sim(self, _state: object) -> int:
        return self.environment_type

    def __getattr__(self, name: str) -> Any:
        values = {
            "current_environment_num": 1,
            "year": 2024,
            "calendar_year": 2024,
            "month": 1,
            "day_of_month": 1,
            "day_of_year": 1,
            "day_of_week": 2,
            "hour": 1,
            "minutes": 15,
            "current_time": 0.25,
            "current_sim_time": 0.25,
            "zone_time_step_number": 1,
            "num_time_steps_in_hour": 4,
        }
        if name not in values:
            raise AttributeError(name)
        return lambda _state: values[name]


def settings(tmp_path: Path) -> SensorSettings:
    required = (
        ("zone_mean_air_temperature.Z", SensorScope.ZONE),
        ("zone_occupant_count.Z", SensorScope.ZONE),
        ("outdoor_dry_bulb", SensorScope.ENVIRONMENT),
        ("outdoor_relative_humidity", SensorScope.ENVIRONMENT),
        ("facility_demand_rate", SensorScope.BUILDING),
    )
    definitions = tuple(
        SensorDefinition(
            logical_id, logical_id, ExchangeKind.VARIABLE, logical_id, "Z", "",
            scope, True
        )
        for logical_id, scope in required
    ) + (
        SensorDefinition(
            "facility_electricity", "Facility", ExchangeKind.METER,
            "Electricity:Facility", "", "J", SensorScope.BUILDING, True
        ),
        SensorDefinition(
            "hvac_electricity", "HVAC", ExchangeKind.METER,
            "Electricity:HVAC", "", "J", SensorScope.BUILDING, True
        ),
    )
    return SensorSettings(
        tmp_path, tmp_path / "current", "a.jsonl", "a.csv", "d.csv", "m.json",
        "v.json", 1, 3, 1, 1, definitions, ("Z",), ()
    )


def test_collector_skips_unready_warmup_non_weather_and_duplicates(tmp_path: Path) -> None:
    collector = SensorCollector(settings(tmp_path))
    collector.registry = Registry()  # type: ignore[assignment]
    writer = Writer()
    collector.writers = writer  # type: ignore[assignment]
    exchange = Exchange()
    callback = collector.callback(SimpleNamespace(exchange=exchange))
    exchange.ready = False
    callback(object())
    exchange.ready = True
    exchange.warmup = True
    callback(object())
    exchange.warmup = False
    exchange.environment_type = 1
    callback(object())
    exchange.environment_type = 3
    callback(object())
    callback(object())
    assert collector.counters.calls_before_data_readiness == 1
    assert collector.counters.warmup_calls_skipped == 1
    assert collector.counters.non_weather_environments_skipped == 1
    assert collector.counters.successful_snapshots == 1
    assert collector.counters.duplicate_snapshots_rejected == 1
    assert len(writer.rows) == 1
    assert not collector.callback_errors
