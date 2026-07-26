from dataclasses import FrozenInstanceError

import pytest
from src.control.models import SAFETY_GUARD_PENDING, ControlCommand
from src.control.reason_codes import ControllerMode, DecisionReason

from tests.control_helpers import settings


def test_command_is_immutable_causal_and_expires() -> None:
    actuator = settings().actuator
    command = ControlCommand(
        "id",
        "decision",
        "space3_1",
        "SPACE3-1",
        actuator,
        24.0,
        1,
        2,
        3,
        False,
        ControllerMode.OCCUPIED_NORMAL,
        DecisionReason.APPLY_OCCUPIED_NORMAL,
        False,
        "f" * 64,
    )
    with pytest.raises(FrozenInstanceError):
        command.command_id = "x"  # type: ignore[misc]
    assert command.expires_after_sequence == 3
    assert SAFETY_GUARD_PENDING == "not_implemented_module_8_pending"


def test_command_rejects_invalid_setpoint() -> None:
    with pytest.raises(ValueError):
        ControlCommand(
            "id",
            "d",
            "z",
            "Z",
            settings().actuator,
            None,
            1,
            2,
            3,
            False,
            ControllerMode.NATIVE,
            DecisionReason.NO_ACTION,
            False,
            "f",
        )
