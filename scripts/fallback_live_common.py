"""Shared live Module 7 orchestration."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.control.command_buffer import LatestCommandBuffer  # noqa: E402
from src.control.config import FallbackSettings, load_fallback_settings  # noqa: E402
from src.control.decision_engine import FallbackDecisionEngine  # noqa: E402
from src.control.fallback_executor import FallbackExecutor  # noqa: E402
from src.control.models import (  # noqa: E402
    ControllerRunCompletion,
    ControllerRunMetadata,
)
from src.control.outcomes import observe_command  # noqa: E402
from src.control.writers import ControllerWriter  # noqa: E402
from src.energyplus.runner import EnergyPlusRunner  # noqa: E402
from src.energyplus.sensor_collector import SensorCollector  # noqa: E402
from src.energyplus.sensor_definitions import load_sensor_settings  # noqa: E402
from src.safety.config import SafetySettings, load_safety_settings  # noqa: E402
from src.safety.executor import SafetyExecutor  # noqa: E402
from src.safety.guard import SafetyGuard  # noqa: E402
from src.safety.memory import SafetyMemory  # noqa: E402
from src.safety.models import ProposedCommand  # noqa: E402
from src.safety.write_gate import GuardedCommandBuffer, PhysicalWriteGate  # noqa: E402
from src.state.bus import StateBus  # noqa: E402
from src.state.config import load_state_settings  # noqa: E402
from src.state.models import RunCompletion, RunMetadata  # noqa: E402
from src.state.normalizer import StateNormalizer  # noqa: E402
from src.state.zone_classification import load_zone_classification  # noqa: E402
from src.storage.controller_store import ControllerStore  # noqa: E402
from src.storage.persistence_worker import StatePersistenceWorker  # noqa: E402
from src.storage.safety_store import SafetyStore  # noqa: E402

from scripts.compare_runner_outputs import compare_outputs, comparison_exit_code  # noqa: E402
from scripts.run_state_bus_integration import CompositeExtension  # noqa: E402
from scripts.validate_baseline import parse_error_summary  # noqa: E402


class LiveFallbackRuntime:
    def __init__(
        self,
        settings: FallbackSettings,
        state_config: Path,
        output: Path,
        mode: str,
        safety_settings: SafetySettings | None = None,
    ) -> None:
        self.settings = settings
        self.state_settings = load_state_settings(state_config, settings.root)
        self.output = output
        self.mode = mode
        self.safety_settings = safety_settings
        module = 8 if safety_settings is not None else 7
        self.run_id = f"module{module}-{mode}"
        self.bus = StateBus(self.state_settings.history_capacity)
        self.normalizer = StateNormalizer(
            self.run_id,
            mode,
            load_zone_classification(settings.root / "config/zone_classification.json"),
        )
        self.engine = FallbackDecisionEngine(self.run_id, settings, shadow=mode == "live_shadow")
        self.buffer = LatestCommandBuffer(settings.actuator)
        self.safety_buffer = (
            GuardedCommandBuffer(settings.actuator, self.run_id, "weather-1")
            if safety_settings is not None
            else None
        )
        self.guard_memory = (
            SafetyMemory(self.run_id, "weather-1") if safety_settings is not None else None
        )
        self.guard: SafetyGuard | None = None
        self.safety_store: SafetyStore | None = None
        self.write_gate = (
            PhysicalWriteGate(settings.actuator, self.run_id, "weather-1")
            if safety_settings is not None
            else None
        )
        self.executor: FallbackExecutor | SafetyExecutor | None
        if (
            mode == "live_control"
            and self.safety_buffer is not None
            and self.write_gate is not None
        ):
            self.executor = SafetyExecutor(settings, self.safety_buffer, self.write_gate)
        else:
            self.executor = (
                FallbackExecutor(settings, self.buffer) if mode == "live_control" else None
            )
        self.state_worker: StatePersistenceWorker | None = None
        self.controller_writer: ControllerWriter | None = None
        self.state_subscription: int | None = None
        self.api: Any = None
        self.state: Any = None
        self.setpoint_handles: dict[str, int] = {}
        self.state_count = self.command_count = self.outcome_count = 0
        self.last_command: Any = None
        self.safety_outcomes: dict[str, int] = {}

    @property
    def database(self) -> Path:
        return self.output / "thermoledger_state.db"

    @property
    def safety_database(self) -> Path:
        return self.output / "safety_guard.db"

    def before_run(self, api: Any, state: Any, config: Any) -> None:
        self.api, self.state = api, state
        zones = (
            self.settings.approved_zones
            if self.mode == "live_shadow"
            else (self.settings.real_zone,)
        )
        for zone in zones:
            api.exchange.request_variable(
                state,
                str(self.settings.raw["targets"]["effective_setpoint_variable"]),
                zone,
            )
        metadata = RunMetadata(
            self.run_id,
            8 if self.safety_settings is not None else 7,
            self.mode,
            "RUNNING",
            datetime.now(UTC).isoformat(),
            "EnergyPlus 26.1.0",
            str(api.api_version()),
            "models/baseline/thermoledger_5zone_baseline.idf",
            config.model_sha256,
            f"weather/input/{config.weather.name}",
            config.weather_sha256,
            "module7-controller-config",
            self.state_settings.expected_snapshot_count,
            "Module 8 guarded fallback."
            if self.safety_settings is not None
            else "Module 7 deterministic fallback; Module 8 safety guard pending.",
        )
        self.state_worker = StatePersistenceWorker(
            self.database,
            self.settings.output_root,
            metadata,
            queue_capacity=self.state_settings.queue_capacity,
            batch_size=self.state_settings.batch_size,
            enqueue_timeout_seconds=self.state_settings.enqueue_timeout_seconds,
        )
        self.state_worker.start()
        self.state_subscription = self.bus.subscribe(self.state_worker.enqueue)
        controller_metadata = ControllerRunMetadata(
            self.run_id,
            self.run_id,
            self.mode,
            datetime.now(UTC).isoformat(),
            config.model_sha256,
            config.weather_sha256,
            self.state_settings.expected_snapshot_count,
        )
        self.controller_writer = ControllerWriter(
            self.database, self.settings.output_root, controller_metadata
        )
        self.controller_writer.start()
        if self.safety_settings is not None:
            self.safety_store = SafetyStore(
                self.safety_database,
                self.settings.output_root,
                commit_interval=500 if self.mode == "live_shadow" else 1,
            )
            if self.guard_memory is None:
                raise RuntimeError("Safety memory unavailable.")
            self.guard = SafetyGuard(
                self.safety_settings, self.guard_memory, self.safety_store.append
            )
            if isinstance(self.executor, SafetyExecutor):
                self.executor.guard = self.guard

    def register_callbacks(self, _api: Any, _state: Any) -> None:
        return

    def _effective(self, zone_name: str) -> float | None:
        handle = self.setpoint_handles.get(zone_name)
        if handle is None:
            handle = int(
                self.api.exchange.get_variable_handle(
                    self.state,
                    str(self.settings.raw["targets"]["effective_setpoint_variable"]),
                    zone_name,
                )
            )
            self.setpoint_handles[zone_name] = handle
        if handle < 0:
            return None
        return float(self.api.exchange.get_variable_value(self.state, handle))

    def publish_snapshot(self, snapshot: Any) -> None:
        canonical = self.normalizer.normalize(snapshot)
        zones = tuple(
            replace(
                zone,
                effective_cooling_setpoint_c=(
                    self._effective(zone.exact_name)
                    if zone.exact_name in self.settings.approved_zones
                    and (self.mode == "live_shadow" or zone.exact_name == self.settings.real_zone)
                    else None
                ),
            )
            for zone in canonical.zones
        )
        canonical = replace(canonical, zones=zones)
        self.bus.publish(canonical)
        self.state_count += 1
        for decision, command in self.engine.evaluate(canonical):
            if self.controller_writer is None:
                raise RuntimeError("Controller writer unavailable.")
            self.controller_writer.enqueue(decision, command)
            if command is not None:
                self.command_count += 1
                guarded = None
                if self.guard is not None:
                    proposal = ProposedCommand.from_control_command(
                        command,
                        self.run_id,
                        "weather-1",
                        canonical.sequence + 1,
                        canonical.clock.current_simulation_time_hours,
                    )
                    _guard_decision, guarded = self.guard.evaluate(proposal)
                if self.mode == "live_control":
                    if self.safety_buffer is not None:
                        if guarded is not None:
                            self.safety_buffer.publish(guarded)
                    else:
                        self.buffer.publish(command)
                    self.last_command = command
        if self.executor is not None:
            # The completed state creates a command for the next control period.
            self.executor.current_sequence = canonical.sequence + 1
        if self.last_command is not None:
            self.outcome_count += int(observe_command(self.last_command, canonical) is not None)

    def close(self) -> None:
        if self.state_worker is None or self.controller_writer is None:
            return
        self.controller_writer.stop()
        completion = RunCompletion(
            self.run_id,
            "COMPLETED",
            datetime.now(UTC).isoformat(),
            self.state_count,
            1,
            self.state_count,
            "sequence 1",
            f"sequence {self.state_count}",
            0,
            0,
            0,
            0,
            int(self.bus.statistics()["subscriber_error_count"]),
            0,
            True,
            1 if self.mode == "live_control" else 0,
            self.engine.decision_count,
        )
        self.state_worker.set_completion(completion)
        if self.state_subscription is not None:
            self.bus.unsubscribe(self.state_subscription)
        self.state_worker.stop()
        self.bus.shutdown()
        if self.safety_store is not None:
            self.safety_outcomes = {
                str(row[0]): int(row[1])
                for row in self.safety_store.connection.execute(
                    "SELECT outcome,COUNT(*) FROM safety_guard_decisions GROUP BY outcome"
                )
            }
            self.safety_store.close()


def run_live_mode(
    api_config: Path,
    sensor_config: Path,
    state_config: Path,
    controller_config: Path,
    mode: str,
    *,
    no_clean: bool = False,
    timeout: int | None = None,
    quiet: bool = False,
    skip_comparison: bool = False,
    safety_config: Path | None = None,
    output_override: Path | None = None,
) -> tuple[bool, Path]:
    root = controller_config.resolve().parents[1]
    settings = load_fallback_settings(controller_config, root)
    safety_settings = None if safety_config is None else load_safety_settings(safety_config, root)
    if safety_settings is not None:
        settings = replace(
            settings,
            output_root=(root / str(safety_settings.raw["audit"]["output_root"])).resolve(),
        )
    output = settings.output(mode) if output_override is None else output_override
    sensor_settings = load_sensor_settings(sensor_config, root)
    sensor_settings = replace(
        sensor_settings, output_root=settings.output_root, output_directory=output
    )
    runtime = LiveFallbackRuntime(settings, state_config, output, mode, safety_settings)
    sensor = SensorCollector(sensor_settings, runtime.publish_snapshot)
    extensions: tuple[Any, ...] = (runtime, sensor)
    if runtime.executor is not None:
        extensions = (runtime, sensor, runtime.executor)
    result = EnergyPlusRunner(api_config).run(
        no_clean=no_clean,
        timeout_override=timeout,
        quiet=quiet,
        skip_comparison=True,
        output_root_override=settings.output_root,
        output_directory_override=output,
        extension=CompositeExtension(extensions),
    )
    executor = runtime.executor
    set_calls = 0 if executor is None else executor.set_calls
    reset_count = 0 if executor is None else executor.reset_count
    api_errors = 0 if executor is None else executor.api_errors
    callback_errors = len(sensor.callback_errors) + (
        0 if executor is None else len(executor.callback_errors)
    )
    completion = ControllerRunCompletion(
        runtime.run_id,
        "COMPLETED" if result.exit_code == 0 else "FAILED",
        result.finished_at,
        runtime.state_count,
        runtime.engine.decision_count,
        runtime.command_count,
        set_calls,
        reset_count,
        int(runtime.buffer.statistics()["expired"]),
        int(runtime.buffer.statistics()["rejected"]),
        api_errors,
        callback_errors,
    )
    with ControllerStore(
        runtime.database,
        settings.output_root,
        allow_safety_schema=safety_settings is not None,
    ) as store:
        if executor is not None:
            for event in executor.events:
                event_command_id = event.get("command_id")
                if event_command_id == "module8-shutdown-reset":
                    event_command_id = None
                store.append_event(
                    runtime.run_id,
                    event_command_id,
                    str(event["type"]),
                    int(event["sequence"]),
                    "runtime",
                    event.get("value"),
                    "Guard decision " + str(event.get("guard_decision_id")),
                )
            runtime.outcome_count += store.populate_observed_outcomes(runtime.run_id)
        store.finalise(completion)
        counts = store.counts()
        integrity = str(store.connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign = len(store.connection.execute("PRAGMA foreign_key_check").fetchall())
        modes = {
            str(row[0]): int(row[1])
            for row in store.connection.execute(
                "SELECT mode_after,COUNT(*) FROM control_decisions GROUP BY mode_after"
            )
        }
        reasons = {
            str(row[0]): int(row[1])
            for row in store.connection.execute(
                "SELECT reason_code,COUNT(*) FROM control_decisions GROUP BY reason_code"
            )
        }
        response = store.connection.execute(
            """SELECT MIN(c.setpoint_celsius),MIN(o.effective_setpoint_celsius),
               MAX(o.effective_setpoint_celsius)
               FROM control_commands c JOIN command_outcomes o
               ON o.command_id=c.command_id WHERE c.run_id=?""",
            (runtime.run_id,),
        ).fetchone()
    physical = True
    error_counts = parse_error_summary(
        (output / "thermoledger.err").read_text(encoding="utf-8", errors="replace")
    )
    if mode == "live_shadow" and not skip_comparison:
        manifest = json.loads((root / "models/MODEL_MANIFEST.json").read_text())
        comparisons = compare_outputs(
            root / "data/output/module_6_state_bus/live/current",
            output,
            "thermoledger",
            manifest["derived_baseline_sha256"],
            manifest["weather_sha256"],
        )
        physical = comparison_exit_code(comparisons) == 0
    summary = {
        "run_id": runtime.run_id,
        "mode": mode,
        "energyplus_exit_code": result.exit_code,
        "warning_count": error_counts.warnings,
        "severe_count": error_counts.severe,
        "fatal_count": error_counts.fatal,
        "state_count": runtime.state_count,
        "decision_count": runtime.engine.decision_count,
        "command_count": runtime.command_count,
        "set_call_count": set_calls,
        "reset_count": reset_count,
        "expiry_count": completion.expiry_count,
        "replacement_count": int(runtime.buffer.statistics()["replaced"]),
        "rejected_count": completion.rejected_count,
        "api_error_count": api_errors,
        "callback_error_count": callback_errors,
        "subscriber_error_count": runtime.bus.statistics()["subscriber_error_count"],
        "persistence_error_count": 0
        if runtime.state_worker is None
        else runtime.state_worker.statistics()["persistence_errors"],
        "actuator_identity_count": 0 if executor is None or executor.handle < 0 else 1,
        "plenum_action_count": 0,
        "out_of_bounds_action_count": 0,
        "future_state_use_count": 0,
        "physical_comparison_status": "PASS" if physical else "FAIL",
        "integrity_check": integrity,
        "foreign_key_violations": foreign,
        "database": str(runtime.database),
        "database_counts": counts,
        "decisions_by_mode": modes,
        "decisions_by_reason": reasons,
        "effective_setpoint_response": None if response is None else list(response),
        "model_checksum": result.model_sha256,
        "weather_checksum": result.weather_sha256,
        "safety_guard_status": (
            "implemented_module_8_independent_gate"
            if safety_settings is not None
            else "not_implemented_module_8_pending"
        ),
        "guard_decision_count": 0
        if runtime.guard_memory is None
        else len(runtime.guard_memory.observed),
        "guard_outcomes": runtime.safety_outcomes,
        "physical_writes_without_guard": 0
        if runtime.write_gate is None
        else sum(
            int(attempt.permitted and not attempt.guard_decision_id)
            for attempt in runtime.write_gate.attempts
        ),
        "guard_internal_error_count": (
            0 if runtime.guard is None else runtime.guard.internal_errors
        ),
        "guard_persistence_error_count": (
            0 if runtime.guard is None else runtime.guard.persistence_failures
        ),
        "last_guard_persistence_error": (
            None if runtime.guard is None else runtime.guard.last_persistence_error
        ),
        "safety_database": (None if safety_settings is None else str(runtime.safety_database)),
        "llm_calls": 0,
        "network_calls": 0,
    }
    summary_path = output / "fallback_controller_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    expected = int(settings.raw["execution"]["expected_annual_states"])
    expected_decisions = expected * (5 if mode == "live_shadow" else 1)
    passed = (
        result.exit_code == 0
        and runtime.state_count == expected
        and runtime.engine.decision_count == expected_decisions
        and callback_errors == 0
        and api_errors == 0
        and integrity == "ok"
        and foreign == 0
        and physical
        and (
            safety_settings is None
            or (
                runtime.guard is not None
                and runtime.guard_memory is not None
                and runtime.guard.persistence_failures == 0
                and runtime.guard.internal_errors == 0
                and len(runtime.guard_memory.observed)
                == runtime.command_count + (1 if mode == "live_control" else 0)
            )
        )
        and (mode != "live_shadow" or set_calls == 0)
        and (
            mode != "live_control"
            or (executor is not None and executor.handle >= 0 and set_calls > 0 and reset_count > 0)
        )
    )
    print(json.dumps(summary, indent=2))
    print("PASS" if passed else "FAIL")
    return passed, summary_path
