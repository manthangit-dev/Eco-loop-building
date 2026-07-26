from typing import Any

import pytest
from src.control.models import ActuatorIdentity
from src.safety.guard import SafetyGuard
from src.safety.models import GuardOutcome, SafetyReason

from tests.safety_helpers import memory, proposal, safety_settings


def evaluate(**changes: Any) -> tuple[GuardOutcome, SafetyReason, float | None]:
    decision, command = SafetyGuard(safety_settings(), memory()).evaluate(proposal(**changes))
    return decision.outcome, decision.reason, None if command is None else command.applied_value


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"zone": "PLENUM-1"}, SafetyReason.PLENUM_ZONE_REJECTED),
        ({"zone": "SPACE2-1"}, SafetyReason.UNAPPROVED_ZONE),
        ({"run_id": "other"}, SafetyReason.WRONG_RUN_ID),
        ({"environment_id": "other"}, SafetyReason.WRONG_ENVIRONMENT),
        ({"warmup": True}, SafetyReason.WARMUP_STATE_REJECTED),
        ({"api_ready": False}, SafetyReason.SIMULATION_NOT_READY),
        ({"schema_version": 2}, SafetyReason.UNSUPPORTED_SCHEMA_VERSION),
    ],
)
def test_fail_closed_identity_phase_and_schema(
    changes: dict[str, object], reason: SafetyReason
) -> None:
    outcome, actual, _ = evaluate(**changes)
    assert outcome in {GuardOutcome.REJECT_NO_WRITE, GuardOutcome.RESET_TO_NATIVE}
    assert actual == reason


def test_allow_and_marginal_absolute_clamp() -> None:
    assert evaluate(value=24.0) == (GuardOutcome.ALLOW, SafetyReason.ALLOWED, 24.0)
    assert evaluate(value=21.9) == (GuardOutcome.CLAMP, SafetyReason.CLAMPED_ABSOLUTE_BOUND, 22.0)


def test_far_out_of_bounds_resets() -> None:
    outcome, reason, _ = evaluate(value=10.0)
    assert (outcome, reason) == (GuardOutcome.RESET_TO_NATIVE, SafetyReason.OUT_OF_ABSOLUTE_BOUNDS)


def test_exact_duplicate_is_idempotent_and_conflict_rejected() -> None:
    guard = SafetyGuard(safety_settings(), memory())
    first = guard.evaluate(proposal())
    assert guard.evaluate(proposal()) == first
    conflict = guard.evaluate(proposal(value=25.0))[0]
    assert conflict.reason == SafetyReason.CONFLICTING_DUPLICATE


def test_rate_limit_and_last_safe_recovery() -> None:
    guard = SafetyGuard(safety_settings(), memory())
    guard.evaluate(proposal("one", 24.0))
    decision, command = guard.evaluate(
        proposal(
            "two",
            26.0,
            source_state_sequence=2,
            decision_sequence=2,
            valid_from_sequence=3,
            expires_after_sequence=4,
            current_sequence=3,
        )
    )
    assert decision.reason == SafetyReason.CLAMPED_RATE_LIMIT
    assert command is not None and command.applied_value == 25.61


def test_exact_actuator_identity() -> None:
    wrong = ActuatorIdentity("Zone Temperature Control", "Cooling Setpoint", "space3-1", "C")
    assert evaluate(actuator=wrong)[1] == SafetyReason.UNAPPROVED_ACTUATOR_KEY


def test_persistence_failure_fails_closed() -> None:
    def fail(*_args: object) -> None:
        raise OSError("disk")

    decision, command = SafetyGuard(safety_settings(), memory(), fail).evaluate(proposal())
    assert decision.reason == SafetyReason.PERSISTENCE_FAILURE_FAIL_CLOSED and command is None
