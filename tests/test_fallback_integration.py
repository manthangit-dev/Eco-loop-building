from scripts.fallback_live_common import LiveFallbackRuntime

from tests.control_helpers import settings
from tests.state_helpers import ROOT


def test_runtime_database_is_scoped_to_output() -> None:
    output = settings().output("live_control")
    runtime = LiveFallbackRuntime(
        settings(), ROOT / "config/state_bus.yaml", output, "live_control"
    )
    assert runtime.database.parent == output
    assert runtime.executor is not None
