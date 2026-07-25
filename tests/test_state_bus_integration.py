from typing import Any

from scripts.run_state_bus_integration import CompositeExtension


class Extension:
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events

    def before_run(self, _api: Any, _state: Any, _config: Any) -> None:
        self.events.append(f"before:{self.name}")

    def register_callbacks(self, _api: Any, _state: Any) -> None:
        self.events.append(f"register:{self.name}")

    def close(self) -> None:
        self.events.append(f"close:{self.name}")


def test_composite_starts_in_order_and_closes_in_reverse() -> None:
    events: list[str] = []
    composite = CompositeExtension((Extension("publisher", events), Extension("sensor", events)))
    composite.before_run(None, None, None)
    composite.register_callbacks(None, None)
    composite.close()
    assert events == [
        "before:publisher",
        "before:sensor",
        "register:publisher",
        "register:sensor",
        "close:sensor",
        "close:publisher",
    ]
