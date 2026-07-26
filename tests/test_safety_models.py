import pytest
from src.safety.models import GuardedCommand, GuardOutcome, SafetyReason, numeric_reason

from tests.safety_helpers import proposal


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        (None, SafetyReason.MISSING_VALUE),
        (True, SafetyReason.NON_NUMERIC_VALUE),
        ("24", SafetyReason.NON_NUMERIC_VALUE),
        (float("nan"), SafetyReason.NAN_VALUE),
        (float("inf"), SafetyReason.POSITIVE_INFINITY),
        (float("-inf"), SafetyReason.NEGATIVE_INFINITY),
    ],
)
def test_numeric_rejections(value: object, reason: SafetyReason) -> None:
    assert numeric_reason(value) == reason


def test_proposal_fingerprint_is_deterministic() -> None:
    assert proposal().fingerprint == proposal().fingerprint


def test_guarded_command_constructor_is_private() -> None:
    with pytest.raises(TypeError):
        GuardedCommand(_token=object(), authority_fingerprint="forged")
    assert GuardOutcome.ALLOW.value == "ALLOW"
