from pathlib import Path

import pytest
from src.energyplus.sensor_definitions import (
    ExchangeKind,
    SensorDefinition,
    SensorScope,
    SensorSettings,
)
from src.energyplus.sensor_registry import SensorRegistry


class Exchange:
    def __init__(self, handles: dict[str, int], *, ready: bool = True) -> None:
        self.handles = handles
        self.ready = ready
        self.requests: list[tuple[str, str]] = []
        self.error = False

    def request_variable(self, _state: object, name: str, key: str) -> None:
        self.requests.append((name, key))

    def api_data_fully_ready(self, _state: object) -> bool:
        return self.ready

    def reset_api_error_flag(self, _state: object) -> None:
        self.error = False

    def api_error_flag(self, _state: object) -> bool:
        return self.error

    def get_variable_handle(self, _state: object, name: str, key: str) -> int:
        return self.handles.get(f"{name}:{key}", -1)

    def get_meter_handle(self, _state: object, name: str) -> int:
        return self.handles.get(name, -1)

    def get_variable_value(self, _state: object, _handle: int) -> float:
        return 0.0

    def get_meter_value(self, _state: object, _handle: int) -> float:
        return 12.5

    def list_available_api_data_csv(self, _state: object) -> bytes:
        return b"what,name,key\nVariable,x,y\n"


def settings(tmp_path: Path) -> SensorSettings:
    variable = SensorDefinition(
        "v", "V", ExchangeKind.VARIABLE, "Variable", "Key", "C",
        SensorScope.ZONE, True
    )
    meter = SensorDefinition(
        "m", "M", ExchangeKind.METER, "Meter", "", "J",
        SensorScope.BUILDING, False
    )
    return SensorSettings(
        tmp_path, tmp_path / "current", "a.jsonl", "a.csv", "available.csv",
        "manifest.json", "validation.json", 1, 3, 1, 1, (variable, meter), ("Z",), ()
    )


def test_registry_requests_only_variables_and_preserves_zero(tmp_path: Path) -> None:
    config = settings(tmp_path)
    config.output_directory.mkdir()
    exchange = Exchange({"Variable:Key": 4, "Meter": 5})
    registry = SensorRegistry(config, config.output_directory)
    registry.request_variables(exchange, object())
    assert exchange.requests == [("Variable", "Key")]
    assert registry.initialize(exchange, object())
    assert registry.read(exchange, object(), "v") == 0.0
    assert registry.read(exchange, object(), "m") == 12.5
    registry.capture_available_data(exchange, object())
    registry.capture_available_data(exchange, object())
    assert (config.output_directory / "available.csv").read_bytes().startswith(b"what")


def test_registry_waits_for_readiness_and_fails_required_handle(tmp_path: Path) -> None:
    config = settings(tmp_path)
    exchange = Exchange({}, ready=False)
    registry = SensorRegistry(config, config.output_directory)
    assert not registry.initialize(exchange, object())
    assert not registry.initialized
    exchange.ready = True
    assert not registry.initialize(exchange, object())
    assert registry.initialized
    assert not registry.required_ready
    assert registry.handle_for("m") is None
    with pytest.raises(RuntimeError, match="not ready"):
        registry.read(exchange, object(), "v")

