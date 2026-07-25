from pathlib import Path

from src.energyplus.actuator_controller import ActuatorController
from src.energyplus.actuator_definitions import load_actuator_settings
from src.energyplus.actuator_plan import build_plan

ROOT = Path(__file__).resolve().parents[1]


def test_controller_rejects_unapproved_run_type() -> None:
    settings = load_actuator_settings(ROOT / "config/actuators.yaml", ROOT)
    try:
        ActuatorController(settings, build_plan(settings), "automatic", Path("."), ("SPACE3-1",))
    except ValueError as exc:
        assert "control or intervention" in str(exc)
    else:
        raise AssertionError("Unsupported run type was accepted.")


def test_control_mode_starts_without_active_override(tmp_path: Path) -> None:
    settings = load_actuator_settings(ROOT / "config/actuators.yaml", ROOT)
    controller = ActuatorController(
        settings, build_plan(settings), "control", tmp_path, ("SPACE3-1",)
    )
    assert controller.run_type == "control"
    assert not controller.override_active
    assert controller.counters.set_calls == 0
