from dataclasses import replace
from pathlib import Path

import pytest
from src.safety.config import load_safety_settings

from tests.safety_helpers import safety_settings


def test_valid_configuration_and_fail_closed_defaults() -> None:
    settings = safety_settings()
    assert settings.schema_version == 1 and settings.fail_closed
    assert settings.minimum == 22.0 and settings.maximum == 30.0


def test_configuration_invariants() -> None:
    settings = safety_settings()
    assert settings.zone == "SPACE3-1"
    assert settings.actuator.unique_key == settings.zone
    assert replace(settings, enabled=False).enabled is False


def test_missing_configuration_fails(tmp_path: Path) -> None:
    path = tmp_path / "safety.yaml"
    path.write_text("safety: {}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_safety_settings(path, tmp_path)
