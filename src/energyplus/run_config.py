"""Typed configuration and safe path resolution for Module 3."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from scripts.validate_baseline import sha256_file

from src.energyplus.api_loader import read_dotenv_value


@dataclass(frozen=True)
class CallbackConfig:
    progress: bool
    message: bool
    begin_environment: bool
    warmup_complete: bool
    maximum_stored_messages: int
    maximum_message_length: int


@dataclass(frozen=True)
class RunnerConfig:
    root: Path
    config_path: Path
    name: str
    energyplus_version: str
    execution_mode: str
    model: Path
    weather: Path
    output_root: Path
    output_directory: Path
    module_2_output: Path
    output_prefix: str
    clean_current_output: bool
    retain_previous_run: str
    timeout_seconds: int
    timeout_grace_seconds: int
    console_output: bool
    validate_after_run: bool
    compare_with_module_2: bool
    callbacks: CallbackConfig
    model_sha256: str
    weather_sha256: str


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping.")
    return value


def _safe_child(path: Path, parent: Path, name: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(parent.resolve())
    except ValueError as exc:
        raise ValueError(f"{name} is outside the approved directory: {resolved}") from exc
    if resolved == parent.resolve():
        raise ValueError(f"{name} must be a child of {parent.resolve()}")
    return resolved


def _resolve_model(
    root: Path, configured: str, expected_hash: str, environ: dict[str, str]
) -> Path:
    configured_path = Path(configured)
    if configured_path.is_absolute():
        raise ValueError("Tracked API runner model path must be repository-relative.")
    candidates = [root / configured_path]
    env_value = environ.get("ENERGYPLUS_IDF_PATH") or read_dotenv_value(
        root / ".env", "ENERGYPLUS_IDF_PATH"
    )
    if env_value:
        candidate = Path(env_value)
        candidates.append(candidate if candidate.is_absolute() else root / candidate)
    for candidate in candidates:
        if candidate.is_file() and sha256_file(candidate) == expected_hash:
            return candidate.resolve()
    raise FileNotFoundError("No configured IDF exists with the Module 2 manifest checksum.")


def _resolve_weather(
    root: Path,
    filename: str,
    energyplus_home: Path,
    expected_hash: str,
    environ: dict[str, str],
) -> Path:
    candidates = [root / "weather" / "input" / filename]
    env_value = environ.get("ENERGYPLUS_WEATHER_PATH") or read_dotenv_value(
        root / ".env", "ENERGYPLUS_WEATHER_PATH"
    )
    if env_value:
        candidate = Path(env_value)
        candidates.append(candidate if candidate.is_absolute() else root / candidate)
    candidates.append(energyplus_home / "WeatherData" / filename)
    for candidate in candidates:
        if candidate.is_file() and sha256_file(candidate) == expected_hash:
            return candidate.resolve()
    raise FileNotFoundError("No configured weather file matches the Module 2 manifest checksum.")


def load_run_config(
    path: Path,
    energyplus_home: Path,
    environ: dict[str, str] | None = None,
    root_override: Path | None = None,
) -> RunnerConfig:
    root = (root_override or repository_root()).resolve()
    env = dict(os.environ if environ is None else environ)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    data = _mapping(raw, "config")
    runner = _mapping(data.get("runner"), "runner")
    paths = _mapping(data.get("paths"), "paths")
    callbacks = _mapping(data.get("callbacks"), "callbacks")
    safety = _mapping(data.get("safety"), "safety")
    if runner.get("execution_mode") != "python_energyplus_runtime_api":
        raise ValueError("Unsupported execution mode.")
    forbidden = (
        "allow_idf_modification",
        "allow_weather_modification",
        "allow_exchange_api",
        "allow_actuator_access",
        "allow_concurrent_in_process_runs",
    )
    if any(bool(safety.get(name)) for name in forbidden):
        raise ValueError(
            "Module 3 safety flags must prohibit modification, exchange, and concurrency."
        )
    manifest = json.loads((root / "models" / "MODEL_MANIFEST.json").read_text(encoding="utf-8"))
    model = _resolve_model(
        root, str(runner["input_model"]), str(manifest["derived_baseline_sha256"]), env
    )
    weather = _resolve_weather(
        root,
        str(runner["weather_filename"]),
        energyplus_home,
        str(manifest["weather_sha256"]),
        env,
    )
    output_root_path = Path(str(runner["output_root"]))
    output_path = Path(str(paths["module_3_output"]))
    module_2_path = Path(str(paths["module_2_output"]))
    if any(path.is_absolute() for path in (output_root_path, output_path, module_2_path)):
        raise ValueError("Tracked output paths must be repository-relative.")
    output_root = (root / output_root_path).resolve()
    output = _safe_child(root / output_path, output_root, "Module 3 output")
    return RunnerConfig(
        root=root,
        config_path=path.resolve(),
        name=str(runner["name"]),
        energyplus_version=str(runner["energyplus_version"]),
        execution_mode=str(runner["execution_mode"]),
        model=model,
        weather=weather,
        output_root=output_root,
        output_directory=output,
        module_2_output=(root / module_2_path).resolve(),
        output_prefix=str(runner["output_prefix"]),
        clean_current_output=bool(runner["clean_current_output"]),
        retain_previous_run=str(runner["retain_previous_run"]),
        timeout_seconds=int(runner["timeout_seconds"]),
        timeout_grace_seconds=int(runner["timeout_grace_seconds"]),
        console_output=bool(runner["console_output"]),
        validate_after_run=bool(runner["validate_after_run"]),
        compare_with_module_2=bool(runner["compare_with_module_2"]),
        callbacks=CallbackConfig(
            progress=bool(callbacks["progress"]),
            message=bool(callbacks["message"]),
            begin_environment=bool(callbacks["begin_environment"]),
            warmup_complete=bool(callbacks["warmup_complete"]),
            maximum_stored_messages=int(callbacks["maximum_stored_messages"]),
            maximum_message_length=int(callbacks["maximum_message_length"]),
        ),
        model_sha256=str(manifest["derived_baseline_sha256"]),
        weather_sha256=str(manifest["weather_sha256"]),
    )


def build_energyplus_arguments(config: RunnerConfig) -> list[str]:
    return [
        "-d",
        str(config.output_directory),
        "-p",
        config.output_prefix,
        "-s",
        "C",
        "-w",
        str(config.weather),
        "-r",
        str(config.model),
    ]
