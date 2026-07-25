import json
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]
from scripts.validate_baseline import sha256_file
from src.energyplus.run_config import build_energyplus_arguments, load_run_config


def _config_data() -> dict[str, Any]:
    return {
        "runner": {
            "name": "test",
            "energyplus_version": "26.1",
            "execution_mode": "python_energyplus_runtime_api",
            "input_model": "models/baseline/model.idf",
            "weather_filename": "weather.epw",
            "output_root": "data/output/module_3_api_runner",
            "output_prefix": "test",
            "clean_current_output": True,
            "retain_previous_run": "timestamped_archive",
            "timeout_seconds": 10,
            "timeout_grace_seconds": 1,
            "console_output": False,
            "validate_after_run": True,
            "compare_with_module_2": True,
        },
        "paths": {
            "module_2_output": "data/output/module_2_baseline/current",
            "module_3_output": "data/output/module_3_api_runner/current",
        },
        "callbacks": {
            "progress": True,
            "message": True,
            "begin_environment": True,
            "warmup_complete": True,
            "maximum_stored_messages": 10,
            "maximum_message_length": 100,
        },
        "safety": {
            "allow_idf_modification": False,
            "allow_weather_modification": False,
            "allow_exchange_api": False,
            "allow_actuator_access": False,
            "allow_concurrent_in_process_runs": False,
        },
    }


def _project(tmp_path: Path) -> tuple[Path, Path]:
    model = tmp_path / "models/baseline/model.idf"
    weather = tmp_path / "weather/input/weather.epw"
    model.parent.mkdir(parents=True)
    weather.parent.mkdir(parents=True)
    model.write_text("model", encoding="utf-8")
    weather.write_text("weather", encoding="utf-8")
    manifest = {
        "derived_baseline_sha256": sha256_file(model),
        "weather_sha256": sha256_file(weather),
    }
    (tmp_path / "models/MODEL_MANIFEST.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    config_path = tmp_path / "config/api_runner.yaml"
    config_path.parent.mkdir()
    config_path.write_text(yaml.safe_dump(_config_data()), encoding="utf-8")
    energyplus_home = tmp_path / "EnergyPlus"
    (energyplus_home / "WeatherData").mkdir(parents=True)
    return config_path, energyplus_home


def test_valid_config_loading(tmp_path: Path) -> None:
    path, home = _project(tmp_path)
    config = load_run_config(path, home, {}, tmp_path)
    assert config.model.name == "model.idf"
    assert config.weather.name == "weather.epw"


def test_missing_idf(tmp_path: Path) -> None:
    path, home = _project(tmp_path)
    (tmp_path / "models/baseline/model.idf").unlink()
    with pytest.raises(FileNotFoundError, match="IDF"):
        load_run_config(path, home, {}, tmp_path)


def test_missing_weather(tmp_path: Path) -> None:
    path, home = _project(tmp_path)
    (tmp_path / "weather/input/weather.epw").unlink()
    with pytest.raises(FileNotFoundError, match="weather"):
        load_run_config(path, home, {}, tmp_path)


def test_invalid_model_checksum(tmp_path: Path) -> None:
    path, home = _project(tmp_path)
    (tmp_path / "models/baseline/model.idf").write_text("changed", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="checksum"):
        load_run_config(path, home, {}, tmp_path)


def test_unsafe_output_path(tmp_path: Path) -> None:
    path, home = _project(tmp_path)
    data = _config_data()
    data["paths"]["module_3_output"] = "models/unsafe"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        load_run_config(path, home, {}, tmp_path)


def test_repository_weather_precedes_environment_path(tmp_path: Path) -> None:
    path, home = _project(tmp_path)
    alternate = tmp_path / "alternate.epw"
    alternate.write_text("weather", encoding="utf-8")
    config = load_run_config(
        path, home, {"ENERGYPLUS_WEATHER_PATH": str(alternate)}, tmp_path
    )
    assert config.weather == (tmp_path / "weather/input/weather.epw").resolve()


def test_absolute_tracked_model_path_rejected(tmp_path: Path) -> None:
    path, home = _project(tmp_path)
    data = _config_data()
    data["runner"]["input_model"] = str(tmp_path / "models/baseline/model.idf")
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="repository-relative"):
        load_run_config(path, home, {}, tmp_path)


def test_program_name_excluded_from_arguments(tmp_path: Path) -> None:
    path, home = _project(tmp_path)
    arguments = build_energyplus_arguments(load_run_config(path, home, {}, tmp_path))
    assert arguments[0] == "-d"
    assert not any("energyplus.exe" in item.lower() for item in arguments)
