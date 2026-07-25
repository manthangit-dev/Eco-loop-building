from pathlib import Path

from src.energyplus.actuator_definitions import load_actuator_settings
from src.energyplus.actuator_registry import ActuatorRegistry

ROOT = Path(__file__).resolve().parents[1]


class Exchange:
    ready = False
    error = False
    calls = 0

    def api_data_fully_ready(self, _state: object) -> bool:
        return self.ready

    def list_available_api_data_csv(self, _state: object) -> bytes:
        return (
            b"**ACTUATORS**\n"
            b"Actuator,Zone Temperature Control,Cooling Setpoint,SPACE3-1,[C]\n"
            b"**VARIABLES**\n"
        )

    def reset_api_error_flag(self, _state: object) -> None:
        self.error = False

    def api_error_flag(self, _state: object) -> bool:
        return self.error

    def get_actuator_handle(self, _state: object, *_triple: str) -> int:
        self.calls += 1
        return 42


def test_registry_waits_then_acquires_exact_handle_once() -> None:
    definition = load_actuator_settings(ROOT / "config/actuators.yaml", ROOT).definition
    registry = ActuatorRegistry(definition, ("SPACE3-1",))
    exchange = Exchange()
    assert not registry.initialize(exchange, object())
    exchange.ready = True
    assert registry.initialize(exchange, object())
    assert registry.initialize(exchange, object())
    assert registry.approved_handle() == 42
    assert exchange.calls == 1
    assert len(registry.discoveries) == 1


def test_registry_rejects_minus_one_handle() -> None:
    definition = load_actuator_settings(ROOT / "config/actuators.yaml", ROOT).definition
    registry = ActuatorRegistry(definition, ("SPACE3-1",))
    exchange = Exchange()
    exchange.ready = True
    exchange.get_actuator_handle = lambda *_args: -1  # type: ignore[method-assign]
    assert not registry.initialize(exchange, object())
