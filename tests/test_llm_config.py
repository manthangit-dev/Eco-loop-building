from pathlib import Path

import pytest
from pydantic import ValidationError
from src.llm.config import load_llm_settings


def test_valid_local_config_and_remote_rejected() -> None:
    root = Path(__file__).resolve().parents[1]
    settings = load_llm_settings(root / "config/llm_supervisor.yaml")
    assert settings.maximum_tool_calls == 6 and settings.local_only
    with pytest.raises(ValidationError):
        settings.model_copy(
            update={"endpoint": "https://api.example.com"}
        ).__class__.model_validate({**settings.model_dump(), "endpoint": "https://api.example.com"})


@pytest.mark.parametrize(
    "field,value",
    [
        ("provider_timeout_seconds", 0),
        ("maximum_tool_calls", 0),
        ("maximum_supervisor_iterations", 100),
    ],
)
def test_unbounded_or_invalid_configuration_rejected(field: str, value: object) -> None:
    root = Path(__file__).resolve().parents[1]
    settings = load_llm_settings(root / "config/llm_supervisor.yaml")
    with pytest.raises(ValidationError):
        settings.__class__.model_validate({**settings.model_dump(), field: value})
