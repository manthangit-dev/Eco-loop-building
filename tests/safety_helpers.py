from pathlib import Path

from src.safety.config import SafetySettings, load_safety_settings
from src.safety.memory import SafetyMemory
from src.safety.models import ProposedCommand


def safety_settings() -> SafetySettings:
    root = Path(__file__).resolve().parents[1]
    return load_safety_settings(root / "config/safety_guard.yaml", root)


def proposal(
    command_id: str = "command-1", value: object = 24.0, **changes: object
) -> ProposedCommand:
    settings = safety_settings()
    values: dict[str, object] = {
        "command_id": command_id,
        "decision_id": "decision-1",
        "run_id": "run-1",
        "environment_id": "environment-1",
        "zone": settings.zone,
        "actuator": settings.actuator,
        "requested_value": value,
        "source_state_sequence": 1,
        "decision_sequence": 1,
        "valid_from_sequence": 2,
        "expires_after_sequence": 3,
        "current_sequence": 2,
        "source_simulation_time_hours": 0.25,
        "decision_simulation_time_hours": 0.25,
        "callback_simulation_time_hours": 0.5,
    }
    values.update(changes)
    return ProposedCommand(**values)  # type: ignore[arg-type]


def memory() -> SafetyMemory:
    return SafetyMemory("run-1", "environment-1")
