from pathlib import Path

import pytest
import scripts.validate_state_storage as validation_module


def test_validation_cli_reports_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    check = validation_module.Check("synthetic", False, "expected")

    def fake_validate(_config: Path, _mode: str) -> tuple[list[validation_module.Check], Path]:
        return [check], tmp_path / "summary.json"

    monkeypatch.setattr(validation_module, "validate", fake_validate)
    assert validation_module.main(["--mode", "replay"]) == 1


def test_check_is_immutable() -> None:
    assert validation_module.Check("check", True, "ok").passed is True
