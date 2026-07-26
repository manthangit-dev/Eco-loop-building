from pathlib import Path

from src.agent.models import ObjectiveType, SupervisorRequest
from src.agent.trusted_fields import TRUSTED_SYSTEM_FIELDS, trusted_control_arguments
from src.control.models import ActuatorIdentity
from src.safety.config import load_safety_settings
from src.safety.guard import SafetyGuard
from src.safety.memory import SafetyMemory
from src.safety.models import ProposedCommand


def request(zone: str = "SPACE3-1") -> SupervisorRequest:
    return SupervisorRequest(
        request_id="trusted-test",
        objective_type=ObjectiveType.ASSESS_CONTROL_PROPOSAL_DRY_RUN,
        objective_text="dry run",
        run_id="module8-live-control",
        environment_id="weather-3",
        state_id=35040,
        zone=zone,
        proposal_value=24.0,
        proposal_units="C",
    )


def test_trusted_fields_ignore_model_causal_metadata() -> None:
    args = trusted_control_arguments(request())
    hostile = {name: "attacker" for name in TRUSTED_SYSTEM_FIELDS}
    assert args["run_id"] != hostile["run_id"]
    assert args["current_sequence"] == 35041
    assert args["valid_from_sequence"] == 35041
    assert args["expires_after_sequence"] == 35042


def evaluate(**overrides: object) -> str:
    args = trusted_control_arguments(request())
    args.update(overrides)
    identity = ActuatorIdentity(
        str(args["component_type"]),
        str(args["control_type"]),
        str(args["actuator_key"]),
        str(args["units"]),
    )
    proposal = ProposedCommand(
        str(args["client_request_id"]),
        "preflight",
        str(args["run_id"]),
        str(args["environment_id"]),
        str(args["zone"]),
        identity,
        args["requested_value"],
        int(args["source_state_sequence"]),
        int(args["decision_sequence"]),
        int(args["valid_from_sequence"]),
        int(args["expires_after_sequence"]),
        int(args["current_sequence"]),
        8760.0,
        8760.0,
        8760.25,
    )
    settings = load_safety_settings(Path("config/safety_guard.yaml"))
    memory = SafetyMemory(str(args["run_id"]), str(args["environment_id"]))
    return SafetyGuard(settings, memory).evaluate(proposal)[0].reason.value


def test_valid_is_not_future_and_adversarial_timing_remains_blocked() -> None:
    assert evaluate() == "allowed"
    assert evaluate(current_sequence=35040) == "command_from_future"
    assert evaluate(current_sequence=35050) == "expired_command"
    assert evaluate(expires_after_sequence=35040) == "expired_command"
    assert evaluate(current_sequence=35043, expires_after_sequence=35050) == "stale_state"
    assert evaluate(zone="PLENUM-1", actuator_key="PLENUM-1") == "plenum_zone_rejected"
