import pytest
from pydantic import ValidationError
from src.mcp_server.models import ControlProposalInput, ToolRequest, canonical_json, fingerprint


def valid_proposal() -> dict[str, object]:
    return {
        "run_id": "run",
        "environment_id": "env",
        "source_state_sequence": 1,
        "current_sequence": 2,
        "component_type": "Zone Temperature Control",
        "control_type": "Cooling Setpoint",
        "actuator_key": "SPACE3-1",
        "zone": "SPACE3-1",
        "units": "C",
        "requested_value": 24.0,
        "client_request_id": "client",
    }


@pytest.mark.parametrize("value", [True, "24", float("nan"), float("inf")])
def test_invalid_numeric_proposal(value: object) -> None:
    with pytest.raises(ValidationError):
        ControlProposalInput.model_validate({**valid_proposal(), "requested_value": value})


def test_request_extra_fields_forbidden_and_serialization_stable() -> None:
    with pytest.raises(ValidationError):
        ToolRequest(request_id="x", tool_name="x", unexpected=True)  # type: ignore[call-arg]
    payload = {"b": None, "a": 1.0}
    assert canonical_json(payload) == '{"a":1.0,"b":null}'
    assert fingerprint(payload) == fingerprint(payload)
