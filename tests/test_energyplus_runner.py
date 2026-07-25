import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import src.energyplus.runner as runner_module
from scripts.compare_runner_outputs import Comparison
from scripts.validate_baseline import Check, Status
from src.energyplus.api_loader import LoadedAPI
from src.energyplus.run_config import CallbackConfig, RunnerConfig
from src.energyplus.run_result import RunStatus
from src.energyplus.runner import EnergyPlusRunner, _prepare_output, run_with_soft_timeout


class FakeRuntime:
    def __init__(self, exit_code: int = 0, invalid_progress: bool = False) -> None:
        self.exit_code = exit_code
        self.invalid_progress = invalid_progress
        self.callbacks: dict[str, Any] = {}
        self.cleared = False
        self.stopped = False
        self.arguments: list[str] = []

    def callback_progress(self, _state: object, callback: Any) -> None:
        self.callbacks["progress"] = callback

    def callback_message(self, _state: object, callback: Any) -> None:
        self.callbacks["message"] = callback

    def callback_begin_new_environment(self, _state: object, callback: Any) -> None:
        self.callbacks["environment"] = callback

    def callback_after_new_environment_warmup_complete(self, _state: object, callback: Any) -> None:
        self.callbacks["warmup"] = callback

    def set_console_output_status(self, _state: object, _enabled: bool) -> None:
        pass

    def run_energyplus(self, state: object, arguments: list[str]) -> int:
        self.arguments = arguments
        self.callbacks["progress"](101 if self.invalid_progress else 100)
        self.callbacks["message"](b"message")
        self.callbacks["environment"](state)
        self.callbacks["warmup"](state)
        return self.exit_code

    def clear_callbacks(self) -> None:
        self.cleared = True

    def stop_simulation(self, _state: object) -> None:
        self.stopped = True


class RaisingRuntime(FakeRuntime):
    def run_energyplus(self, _state: object, _arguments: list[str]) -> int:
        raise RuntimeError("simulated API failure")


class FakeStateManager:
    def __init__(self) -> None:
        self.created = 0
        self.deleted = 0

    def new_state(self) -> object:
        self.created += 1
        return object()

    def delete_state(self, _state: object) -> None:
        self.deleted += 1


class FakeAPI:
    def __init__(self, exit_code: int = 0, invalid_progress: bool = False) -> None:
        self.runtime = FakeRuntime(exit_code, invalid_progress)
        self.state_manager = FakeStateManager()

    def verify_api_version_match(self, _state: object) -> None:
        pass


def _config(tmp_path: Path) -> RunnerConfig:
    model = tmp_path / "model.idf"
    weather = tmp_path / "weather.epw"
    model.write_text("model", encoding="utf-8")
    weather.write_text("weather", encoding="utf-8")
    output_root = tmp_path / "data/output/module_3_api_runner"
    return RunnerConfig(
        root=tmp_path,
        config_path=tmp_path / "config/api_runner.yaml",
        name="test",
        energyplus_version="26.1",
        execution_mode="python_energyplus_runtime_api",
        model=model,
        weather=weather,
        output_root=output_root,
        output_directory=output_root / "current",
        module_2_output=tmp_path / "module2",
        output_prefix="thermoledger",
        clean_current_output=True,
        retain_previous_run="timestamped_archive",
        timeout_seconds=5,
        timeout_grace_seconds=1,
        console_output=False,
        validate_after_run=True,
        compare_with_module_2=True,
        callbacks=CallbackConfig(True, True, True, True, 10, 100),
        model_sha256="model-hash",
        weather_sha256="weather-hash",
    )


def _loaded(tmp_path: Path, api: FakeAPI) -> LoadedAPI:
    library = tmp_path / "EnergyPlusAPI.dll"
    library.write_bytes(b"dll")
    return LoadedAPI(api, tmp_path, "0.2", library, "EnergyPlus 26.1")


def _patch_dependencies(monkeypatch: pytest.MonkeyPatch, config: RunnerConfig) -> None:
    monkeypatch.setattr(runner_module, "load_run_config", lambda *_args, **_kwargs: config)
    monkeypatch.setattr(
        runner_module,
        "validate_run",
        lambda *_args, **_kwargs: ([Check("ok", Status.PASS, "ok")], config.output_directory),
    )
    monkeypatch.setattr(
        runner_module,
        "run_comparison",
        lambda *_args, **_kwargs: (
            [Comparison("ok", True, 1, 1, "match")],
            config.output_directory / "comparison_summary.json",
        ),
    )


def test_runner_creates_state_registers_callbacks_and_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    _patch_dependencies(monkeypatch, config)
    api = FakeAPI()
    result = EnergyPlusRunner().run(loaded_api=_loaded(tmp_path, api))
    assert result.status is RunStatus.PASS
    assert api.state_manager.created == api.state_manager.deleted == 1
    assert api.runtime.cleared
    assert (config.output_directory / "run_metadata.json").is_file()
    assert api.runtime.arguments[0] == "-d"


def test_nonzero_exit_code_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(tmp_path)
    _patch_dependencies(monkeypatch, config)
    result = EnergyPlusRunner().run(loaded_api=_loaded(tmp_path, FakeAPI(exit_code=1)))
    assert result.status is RunStatus.FAIL
    assert result.exit_code == 1


def test_callback_error_fails_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(tmp_path)
    _patch_dependencies(monkeypatch, config)
    result = EnergyPlusRunner().run(loaded_api=_loaded(tmp_path, FakeAPI(invalid_progress=True)))
    assert result.status is RunStatus.FAIL
    assert result.callback_errors


def test_state_deleted_and_callbacks_cleared_after_api_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    _patch_dependencies(monkeypatch, config)
    api = FakeAPI()
    api.runtime = RaisingRuntime()
    result = EnergyPlusRunner().run(loaded_api=_loaded(tmp_path, api))
    assert result.status is RunStatus.FAIL
    assert api.state_manager.deleted == 1
    assert api.runtime.cleared


def test_timeout_requests_stop() -> None:
    stopped = threading.Event()

    class BlockingRuntime:
        def run_energyplus(self, _state: object, _arguments: list[str]) -> int:
            stopped.wait(1)
            return 0

        def stop_simulation(self, _state: object) -> None:
            stopped.set()

    api = SimpleNamespace(runtime=BlockingRuntime())
    _, timed_out, _, _ = run_with_soft_timeout(api, object(), [], 0, 1)
    assert timed_out
    assert stopped.is_set()


def test_safe_output_archives_previous_current(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.output_directory.mkdir(parents=True)
    (config.output_directory / "old.txt").write_text("old", encoding="utf-8")
    _prepare_output(config, no_clean=False)
    assert config.output_directory.is_dir()
    assert list((config.output_root / "archive").iterdir())


def test_no_clean_refuses_existing_output(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.output_directory.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="no-clean"):
        _prepare_output(config, no_clean=True)


def test_concurrent_run_is_rejected() -> None:
    assert runner_module._RUN_LOCK.acquire(blocking=False)
    try:
        with pytest.raises(RuntimeError, match="concurrent"):
            EnergyPlusRunner().run()
    finally:
        runner_module._RUN_LOCK.release()
