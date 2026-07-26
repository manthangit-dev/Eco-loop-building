from pathlib import Path

from scripts.replay_fallback_controller import replay

from tests.state_helpers import ROOT


def test_limited_replay_is_deterministic_and_has_zero_writes(tmp_path: Path) -> None:
    # Output must remain below the configured approved root.
    first = ROOT / "data/output/module_7_fallback_controller/test_replay_one"
    second = ROOT / "data/output/module_7_fallback_controller/test_replay_two"
    source = ROOT / "data/output/module_6_state_bus/replay/current/thermoledger_state.db"
    a = replay(ROOT / "config/fallback_controller.yaml", source, first, 2)
    b = replay(ROOT / "config/fallback_controller.yaml", source, second, 2)
    assert a["decision_content_fingerprint"] == b["decision_content_fingerprint"]
    assert a["actuator_write_count"] == 0
