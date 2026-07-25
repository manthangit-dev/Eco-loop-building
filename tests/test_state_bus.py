import threading

import pytest
from src.state.bus import StateBus
from src.state.models import NonMonotonicSequenceError

from tests.state_helpers import sample_state, with_sequence


def test_bus_bounds_history_tracks_gaps_and_isolates_subscriber_errors() -> None:
    bus = StateBus(2)
    bus.subscribe(lambda _state: (_ for _ in ()).throw(RuntimeError("subscriber")))
    state = sample_state()
    bus.publish(state)
    bus.publish(with_sequence(state, 3))
    bus.publish(with_sequence(state, 4))
    assert [item.sequence for item in bus.recent(10)] == [3, 4]
    stats = bus.statistics()
    assert stats["evicted_state_count"] == 1
    assert stats["sequence_gap_count"] == 1
    assert stats["subscriber_error_count"] == 3


def test_bus_rejects_duplicate_and_wakes_waiter() -> None:
    bus = StateBus(2)
    state = sample_state()
    received: list[int] = []
    waiter = threading.Thread(
        target=lambda: received.append((bus.wait_for_newer(0, 1) or state).sequence)
    )
    waiter.start()
    bus.publish(state)
    waiter.join()
    assert received == [1]
    with pytest.raises(NonMonotonicSequenceError):
        bus.publish(state)
    bus.shutdown()
    with pytest.raises(RuntimeError):
        bus.publish(with_sequence(state, 2))
