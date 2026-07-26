from pathlib import Path

import scripts.validate_fallback_controller as module
from src.control.models import SAFETY_GUARD_PENDING


def test_missing_summary_fails(tmp_path: Path) -> None:
    checks, _ = module.validate(
        Path("config/fallback_controller.yaml").resolve(), "replay_shadow", tmp_path
    )
    assert not all(check.passed for check in checks)


def test_safety_marker_is_required() -> None:
    assert SAFETY_GUARD_PENDING == "not_implemented_module_8_pending"
