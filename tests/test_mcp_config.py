from dataclasses import replace
from pathlib import Path

import pytest
from src.mcp_server.config import load_mcp_settings


def settings_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config/mcp_server.yaml"


def test_valid_local_stdio_configuration() -> None:
    settings = load_mcp_settings(settings_path())
    assert settings.transport == "stdio" and not settings.control_tools_enabled
    assert settings.implementation_version == "1.28.1"


def test_unknown_run_and_control_default() -> None:
    settings = load_mcp_settings(settings_path())
    with pytest.raises(KeyError):
        settings.run_path("unknown")
    assert replace(settings, control_tools_enabled=True).control_tools_enabled


def test_public_network_configuration_rejected(tmp_path: Path) -> None:
    text = settings_path().read_text().replace("host: null", "host: 0.0.0.0")
    path = tmp_path / "mcp.yaml"
    path.write_text(text)
    with pytest.raises(ValueError):
        load_mcp_settings(path)
