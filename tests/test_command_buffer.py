import threading

import pytest
from src.control.command_buffer import LatestCommandBuffer
from src.control.models import ControlCommand
from src.control.reason_codes import ControllerMode, DecisionReason

from tests.control_helpers import settings


def _command(identifier: str = "one", sequence: int = 1) -> ControlCommand:
    return ControlCommand(
        identifier,
        "d",
        "space3_1",
        "SPACE3-1",
        settings().actuator,
        24.0,
        sequence,
        sequence + 1,
        sequence + 2,
        False,
        ControllerMode.OCCUPIED_NORMAL,
        DecisionReason.APPLY_OCCUPIED_NORMAL,
        False,
        "f" * 64,
    )


def test_buffer_publish_expiry_duplicate_clear_shutdown() -> None:
    buffer = LatestCommandBuffer(settings().actuator)
    command = _command()
    buffer.publish(command)
    assert buffer.latest(1) is None and buffer.latest(2) == command
    with pytest.raises(ValueError):
        buffer.publish(command)
    assert buffer.latest(4) is None
    buffer.clear()
    buffer.shutdown()
    with pytest.raises(RuntimeError):
        buffer.publish(_command("two", 2))


def test_buffer_thread_safety() -> None:
    buffer = LatestCommandBuffer(settings().actuator)
    threads = [threading.Thread(target=buffer.statistics) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert buffer.statistics()["published"] == 0
