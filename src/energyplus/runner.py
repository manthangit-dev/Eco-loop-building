"""Concurrency-safe EnergyPlus Runtime API runner for the verified baseline."""

from __future__ import annotations

import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import uuid4

from scripts.compare_runner_outputs import comparison_exit_code, run_comparison
from scripts.validate_baseline import validate_run, validation_exit_code

from src.energyplus.api_loader import LoadedAPI, load_energyplus_api
from src.energyplus.callbacks import CallbackCollector
from src.energyplus.run_config import (
    RunnerConfig,
    build_energyplus_arguments,
    load_run_config,
    repository_root,
)
from src.energyplus.run_result import RunResult, RunStatus

_RUN_LOCK = threading.Lock()
_GENERATED_SUFFIXES = {
    ".csv",
    ".eio",
    ".end",
    ".err",
    ".eso",
    ".htm",
    ".html",
    ".mdd",
    ".mtd",
    ".mtr",
    ".rdd",
    ".rvaudit",
    ".sql",
}


def _installation_outputs(home: Path) -> list[str]:
    files: list[str] = []
    for directory in (home, home / "ExampleFiles"):
        if directory.is_dir():
            files.extend(
                str(path.resolve())
                for path in directory.iterdir()
                if path.is_file()
                and (
                    path.suffix.lower() in _GENERATED_SUFFIXES
                    or path.name.lower().startswith("eplusout.")
                )
            )
    return sorted(files)


def _prepare_output(config: RunnerConfig, no_clean: bool) -> None:
    config.output_root.mkdir(parents=True, exist_ok=True)
    output = config.output_directory
    output.relative_to(config.output_root)
    if not output.exists():
        output.mkdir(parents=True)
        return
    if no_clean:
        raise RuntimeError(f"--no-clean refuses to reuse existing output: {output}")
    if not config.clean_current_output:
        raise RuntimeError(f"Configured output already exists and cleaning is disabled: {output}")
    archive = config.output_root / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    shutil.move(str(output), str(archive / f"current_{stamp}"))
    output.mkdir(parents=True)


def run_with_soft_timeout(
    api: Any,
    state: Any,
    arguments: list[str],
    timeout_seconds: int,
    grace_seconds: int,
) -> tuple[int | None, bool, bool, str]:
    outcome: dict[str, Any] = {}
    completed = threading.Event()

    def target() -> None:
        try:
            outcome["exit_code"] = int(api.runtime.run_energyplus(state, arguments))
        except (RuntimeError, OSError, ValueError, TypeError, AttributeError) as exc:
            outcome["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            completed.set()

    worker = threading.Thread(target=target, name="energyplus-runtime-api", daemon=False)
    worker.start()
    timed_out = not completed.wait(timeout_seconds)
    cancelled = False
    if timed_out:
        api.runtime.stop_simulation(state)
        completed.wait(grace_seconds)
    try:
        while not completed.wait(0.2):
            pass
    except KeyboardInterrupt:
        cancelled = True
        api.runtime.stop_simulation(state)
        completed.wait()
    worker.join()
    return outcome.get("exit_code"), timed_out, cancelled, str(outcome.get("error", ""))


class EnergyPlusRunner:
    def __init__(self, config_path: Path = Path("config/api_runner.yaml")) -> None:
        self.root = repository_root()
        self.config_path = (
            config_path.resolve()
            if config_path.is_absolute()
            else (self.root / config_path).resolve()
        )

    def run(
        self,
        *,
        no_clean: bool = False,
        timeout_override: int | None = None,
        quiet: bool = False,
        skip_validation: bool = False,
        skip_comparison: bool = False,
        loaded_api: LoadedAPI | None = None,
    ) -> RunResult:
        if not _RUN_LOCK.acquire(blocking=False):
            raise RuntimeError("A concurrent in-process EnergyPlus run is not allowed.")
        loaded = loaded_api
        state: Any = None
        callbacks_cleared = False
        state_deleted = False
        started = datetime.now(UTC)
        started_clock = monotonic()
        collector: CallbackCollector | None = None
        config: RunnerConfig | None = None
        result: RunResult | None = None
        try:
            loaded = loaded or load_energyplus_api(self.root)
            config = load_run_config(self.config_path, loaded.energyplus_home)
            _prepare_output(config, no_clean)
            collector = CallbackCollector(
                config.output_directory / "energyplus_api_messages.log",
                config.callbacks.maximum_stored_messages,
                config.callbacks.maximum_message_length,
            )
            arguments = build_energyplus_arguments(config)
            before = _installation_outputs(loaded.energyplus_home)
            api = loaded.api
            state = api.state_manager.new_state()
            api.verify_api_version_match(state)
            if config.callbacks.progress:
                api.runtime.callback_progress(state, collector.progress_callback())
            if config.callbacks.message:
                api.runtime.callback_message(state, collector.message_callback())
            if config.callbacks.begin_environment:
                api.runtime.callback_begin_new_environment(
                    state, collector.begin_environment_callback()
                )
            if config.callbacks.warmup_complete:
                api.runtime.callback_after_new_environment_warmup_complete(
                    state, collector.warmup_complete_callback()
                )
            api.runtime.set_console_output_status(state, config.console_output and not quiet)
            timeout = timeout_override or config.timeout_seconds
            exit_code, timed_out, cancelled, error = run_with_soft_timeout(
                api, state, arguments, timeout, config.timeout_grace_seconds
            )
            finished = datetime.now(UTC)
            result = RunResult(
                run_id=f"api-{uuid4()}",
                status=RunStatus.FAIL,
                execution_mode=config.execution_mode,
                started_at=started.isoformat(),
                finished_at=finished.isoformat(),
                elapsed_seconds=monotonic() - started_clock,
                timed_out=timed_out,
                cancelled=cancelled,
                exit_code=exit_code,
                energyplus_version=loaded.energyplus_version,
                api_version=loaded.api_version,
                api_library_path=str(loaded.api_library_path),
                model_path=str(config.model),
                model_sha256=config.model_sha256,
                weather_path=str(config.weather),
                weather_sha256=config.weather_sha256,
                output_directory=str(config.output_directory),
                command_line_arguments=arguments,
                progress_events=list(collector.progress_events),
                message_count=collector.message_count,
                stored_message_count=len(collector.messages),
                truncated_message_count=collector.truncated_message_count,
                environment_start_count=collector.environment_start_count,
                warmup_complete_count=collector.warmup_complete_count,
                callback_errors=list(collector.errors),
                error_message=error,
                installation_generated_files_before=before,
                installation_generated_files_after=_installation_outputs(
                    loaded.energyplus_home
                ),
            )
        except (
            RuntimeError,
            ValueError,
            OSError,
            TypeError,
            AttributeError,
            KeyboardInterrupt,
        ) as exc:
            if result is None and config is not None and loaded is not None:
                finished = datetime.now(UTC)
                result = RunResult(
                    run_id=f"api-{uuid4()}",
                    status=RunStatus.FAIL,
                    execution_mode=config.execution_mode,
                    started_at=started.isoformat(),
                    finished_at=finished.isoformat(),
                    elapsed_seconds=monotonic() - started_clock,
                    timed_out=False,
                    cancelled=isinstance(exc, KeyboardInterrupt),
                    exit_code=None,
                    energyplus_version=loaded.energyplus_version,
                    api_version=loaded.api_version,
                    api_library_path=str(loaded.api_library_path),
                    model_path=str(config.model),
                    model_sha256=config.model_sha256,
                    weather_path=str(config.weather),
                    weather_sha256=config.weather_sha256,
                    output_directory=str(config.output_directory),
                    command_line_arguments=build_energyplus_arguments(config),
                    error_message=f"{type(exc).__name__}: {exc}",
                )
            elif result is None:
                raise
        finally:
            if loaded is not None and state is not None:
                try:
                    loaded.api.runtime.clear_callbacks()
                    callbacks_cleared = True
                finally:
                    loaded.api.state_manager.delete_state(state)
                    state_deleted = True
            if loaded_api is None and loaded is not None:
                loaded.close()
            _RUN_LOCK.release()

        if result is None or config is None:
            raise RuntimeError("Runner failed before a structured result could be created.")
        result.callbacks_cleared = callbacks_cleared
        result.state_deleted = state_deleted
        metadata_path = config.output_directory / "run_metadata.json"
        result.write_json(metadata_path)

        if config.validate_after_run and not skip_validation:
            checks, _ = validate_run(
                config.root / "config" / "baseline.yaml",
                config.output_directory,
                config.output_root,
            )
            result.validation_status = (
                "PASS" if validation_exit_code(checks) == 0 else "FAIL"
            )
            result.validation_summary_path = str(
                config.output_directory / "validation_summary.json"
            )
        if config.compare_with_module_2 and not skip_comparison:
            comparisons, _ = run_comparison(config.config_path)
            result.comparison_status = (
                "PASS" if comparison_exit_code(comparisons) == 0 else "FAIL"
            )

        callbacks_ok = (
            bool(result.progress_events)
            and result.message_count > 0
            and result.environment_start_count > 0
            and result.warmup_complete_count > 0
            and not result.callback_errors
        )
        required_ok = (
            result.exit_code == 0
            and not result.timed_out
            and not result.cancelled
            and callbacks_ok
            and result.callbacks_cleared
            and result.state_deleted
            and result.validation_status in {"PASS", "NOT_RUN"}
            and result.comparison_status in {"PASS", "NOT_RUN"}
        )
        result.status = RunStatus.PASS if required_ok else RunStatus.FAIL
        if not required_ok and not result.error_message:
            result.error_message = "One or more required runner verification checks failed."
        result.write_json(metadata_path)
        return result
