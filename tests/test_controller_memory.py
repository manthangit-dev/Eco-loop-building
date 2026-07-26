from dataclasses import replace

from src.control.controller_memory import ControllerMemory
from src.control.reason_codes import ControllerMode


def test_memory_is_independent_snapshot_restore_and_reset() -> None:
    memory = ControllerMemory("run")
    first = replace(memory.get("a"), current_mode=ControllerMode.HOLD, active_command=True)
    memory.update(first)
    assert memory.get("b").current_mode is ControllerMode.NATIVE
    snapshot = memory.snapshot(2)
    memory.reset("a", 3)
    assert not memory.get("a").active_command
    memory.restore(snapshot)
    assert memory.get("a").active_command
