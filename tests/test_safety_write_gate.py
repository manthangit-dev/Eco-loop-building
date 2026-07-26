from typing import Any

import pytest
from src.safety.guard import SafetyGuard
from src.safety.write_gate import GuardedCommandBuffer, PhysicalWriteGate

from tests.safety_helpers import memory, proposal, safety_settings


class Exchange:
    def __init__(self) -> None:
        self.sets = 0
        self.resets = 0

    def set_actuator_value(self, *_args: Any) -> None:
        self.sets += 1

    def reset_actuator(self, *_args: Any) -> None:
        self.resets += 1


def test_raw_and_dictionary_bypass_are_blocked() -> None:
    settings = safety_settings()
    buffer = GuardedCommandBuffer(settings.actuator, "run-1", "environment-1")
    with pytest.raises(TypeError):
        buffer.publish(proposal())
    with pytest.raises(TypeError):
        buffer.publish({"approved": True})
    exchange = Exchange()
    gate = PhysicalWriteGate(settings.actuator, "run-1", "environment-1")
    assert not gate.submit(exchange, object(), 1, proposal(), 2)
    assert exchange.sets == exchange.resets == 0


def test_valid_guarded_command_is_written_and_traced() -> None:
    settings = safety_settings()
    _, command = SafetyGuard(settings, memory()).evaluate(proposal())
    assert command is not None
    buffer = GuardedCommandBuffer(settings.actuator, "run-1", "environment-1")
    buffer.publish(command)
    exchange = Exchange()
    gate = PhysicalWriteGate(settings.actuator, "run-1", "environment-1")
    assert gate.submit(exchange, object(), 1, buffer.latest(2), 2)
    assert exchange.sets == 1 and gate.attempts[0].guard_decision_id
