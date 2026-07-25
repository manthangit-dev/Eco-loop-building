import json

from src.energyplus.actuator_events import EVENT_HEADERS, ActuatorEvent, ActuatorEventType


def test_event_json_and_headers_are_deterministic() -> None:
    event = ActuatorEvent(
        1,
        "07-19 14:15",
        ActuatorEventType.OVERRIDE_APPLIED,
        "intervention",
        "SPACE3-1",
        "Zone Temperature Control",
        "Cooling Setpoint",
        "SPACE3-1",
        42,
        23.9,
        24.9,
        24.9,
        24.9,
        11.0,
        False,
        "bounded test",
    )
    payload = json.loads(event.to_json())
    assert payload["event_type"] == "OVERRIDE_APPLIED"
    assert list(event.to_dict()) == EVENT_HEADERS
