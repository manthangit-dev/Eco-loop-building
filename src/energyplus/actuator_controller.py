"""Exception-contained deterministic controller for one approved actuator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from src.energyplus.actuator_definitions import ActuatorSettings
from src.energyplus.actuator_events import ActuatorEvent, ActuatorEventType
from src.energyplus.actuator_plan import ActuatorPlan, WindowPosition
from src.energyplus.actuator_registry import ActuatorRegistry
from src.energyplus.actuator_writers import ActuatorWriters, write_json
from src.energyplus.run_config import RunnerConfig


@dataclass
class ActuatorCounters:
    callback_calls: int = 0
    calls_before_readiness: int = 0
    warmup_calls_skipped: int = 0
    non_weather_calls_skipped: int = 0
    calls_before_intervention: int = 0
    calls_during_intervention: int = 0
    calls_after_intervention: int = 0
    successful_handle_acquisitions: int = 0
    set_calls: int = 0
    unique_zone_timestep_write_periods: int = 0
    reset_calls: int = 0
    rejected_writes: int = 0
    out_of_window_write_attempts: int = 0
    api_error_activations: int = 0
    callback_error_count: int = 0
    first_write_timestamp: str = ""
    last_write_timestamp: str = ""
    reset_timestamp: str = ""
    last_observed_effective_setpoint: float | None = None


class ActuatorController:
    def __init__(
        self,
        settings: ActuatorSettings,
        plan: ActuatorPlan,
        run_type: str,
        output_directory: Any,
        occupied_zones: tuple[str, ...],
    ) -> None:
        if run_type not in {"control", "intervention"}:
            raise ValueError("Run type must be control or intervention.")
        self.settings = settings
        self.plan = plan
        self.run_type = run_type
        self.output_directory = output_directory
        self.registry = ActuatorRegistry(settings.definition, occupied_zones)
        self.counters = ActuatorCounters()
        self.callback_errors: list[str] = []
        self.override_active = False
        self.reset_complete = False
        self.setpoint_handle: int | None = None
        self.occupancy_handle: int | None = None
        self.writer: ActuatorWriters | None = None
        self._sequence = 0
        self._written_periods: set[tuple[int, int, int, int]] = set()
        self._api: Any = None
        self._state: Any = None
        self._actuation_ref: Callable[[Any], None] | None = None
        self._observation_ref: Callable[[Any], None] | None = None

    def before_run(self, api: Any, state: Any, _config: RunnerConfig) -> None:
        self._api, self._state = api, state
        self.writer = ActuatorWriters(
            self.output_directory,
            self.settings.output_root,
            self.settings.event_jsonl,
            self.settings.event_csv,
        )
        api.exchange.request_variable(
            state,
            self.settings.effective_setpoint_variable,
            self.plan.target_zone,
        )
        api.exchange.request_variable(state, "Zone People Occupant Count", self.plan.target_zone)

    def register_callbacks(self, api: Any, state: Any) -> None:
        self._actuation_ref = self.actuation_callback(api)
        self._observation_ref = self.observation_callback(api)
        api.runtime.callback_after_predictor_before_hvac_managers(state, self._actuation_ref)
        api.runtime.callback_end_zone_timestep_after_zone_reporting(state, self._observation_ref)

    @staticmethod
    def _clock(exchange: Any, state: Any) -> tuple[int, int, int, int]:
        return (
            int(exchange.month(state)),
            int(exchange.day_of_month(state)),
            int(exchange.hour(state)),
            int(exchange.minutes(state)),
        )

    @staticmethod
    def _label(clock: tuple[int, int, int, int]) -> str:
        return f"{clock[0]:02d}-{clock[1]:02d} {clock[2]:02d}:{clock[3]:02d}"

    def _emit(
        self,
        event_type: ActuatorEventType,
        clock: tuple[int, int, int, int],
        *,
        effective: float | None = None,
        occupancy: float | None = None,
        api_error: bool = False,
        reason: str = "",
    ) -> None:
        if self.writer is None:
            raise RuntimeError("Actuator writer is unavailable.")
        self._sequence += 1
        self.writer.write(
            ActuatorEvent(
                self._sequence,
                self._label(clock),
                event_type,
                self.run_type,
                self.plan.target_zone,
                self.plan.actuator.component_type,
                self.plan.actuator.control_type,
                self.plan.actuator.unique_key,
                self.registry.handle,
                self.plan.baseline_setpoint,
                self.plan.requested_setpoint,
                self.plan.approved_setpoint,
                effective,
                occupancy,
                api_error,
                reason,
            )
        )

    def _api_call(self, exchange: Any, state: Any, operation: Callable[[], None]) -> None:
        exchange.reset_api_error_flag(state)
        operation()
        if exchange.api_error_flag(state):
            self.counters.api_error_activations += 1
            exchange.reset_api_error_flag(state)
            raise RuntimeError("EnergyPlus actuator API error flag activated.")

    def _ensure_handles(self, exchange: Any, state: Any) -> bool:
        if not self.registry.initialize(exchange, state):
            return False
        if self.setpoint_handle is None:
            self.setpoint_handle = int(
                exchange.get_variable_handle(
                    state,
                    self.settings.effective_setpoint_variable,
                    self.plan.target_zone,
                )
            )
            self.occupancy_handle = int(
                exchange.get_variable_handle(
                    state, "Zone People Occupant Count", self.plan.target_zone
                )
            )
            if self.setpoint_handle == -1 or self.occupancy_handle == -1:
                raise RuntimeError("Required target observation handle is unavailable.")
            self.counters.successful_handle_acquisitions = 1
            clock = self._clock(exchange, state)
            self._emit(ActuatorEventType.HANDLE_ACQUIRED, clock)
        return True

    def actuation_callback(self, api: Any) -> Callable[[Any], None]:
        def actuate(state: Any) -> None:
            try:
                self.counters.callback_calls += 1
                exchange = api.exchange
                if not exchange.api_data_fully_ready(state):
                    self.counters.calls_before_readiness += 1
                    return
                if exchange.warmup_flag(state):
                    self.counters.warmup_calls_skipped += 1
                    return
                if int(exchange.kind_of_sim(state)) != self.settings.weather_environment_type:
                    self.counters.non_weather_calls_skipped += 1
                    return
                if not self._ensure_handles(exchange, state):
                    return
                clock = self._clock(exchange, state)
                position = self.plan.position(*clock)
                if position is WindowPosition.BEFORE:
                    self.counters.calls_before_intervention += 1
                    return
                if position is WindowPosition.DURING:
                    self.counters.calls_during_intervention += 1
                    if self.run_type == "control":
                        return
                    occupancy = float(exchange.get_variable_value(state, self.occupancy_handle))
                    if occupancy <= 0:
                        self.counters.rejected_writes += 1
                        self._emit(
                            ActuatorEventType.WRITE_REJECTED,
                            clock,
                            occupancy=occupancy,
                            reason="Target zone is not occupied.",
                        )
                        return
                    handle = self.registry.approved_handle()
                    self._api_call(
                        exchange,
                        state,
                        lambda: exchange.set_actuator_value(
                            state, handle, self.plan.approved_setpoint
                        ),
                    )
                    event_type = (
                        ActuatorEventType.OVERRIDE_REAPPLIED
                        if self.override_active
                        else ActuatorEventType.OVERRIDE_APPLIED
                    )
                    self.override_active = True
                    self.counters.set_calls += 1
                    period = clock
                    self._written_periods.add(period)
                    self.counters.unique_zone_timestep_write_periods = len(self._written_periods)
                    label = self._label(clock)
                    if not self.counters.first_write_timestamp:
                        self.counters.first_write_timestamp = label
                    self.counters.last_write_timestamp = label
                    self._emit(event_type, clock, occupancy=occupancy)
                    return
                self.counters.calls_after_intervention += 1
                if self.override_active and not self.reset_complete:
                    handle = self.registry.approved_handle()
                    self._api_call(exchange, state, lambda: exchange.reset_actuator(state, handle))
                    self.override_active = False
                    self.reset_complete = True
                    self.counters.reset_calls += 1
                    self.counters.reset_timestamp = self._label(clock)
                    self._emit(ActuatorEventType.OVERRIDE_RESET, clock)
            except BaseException as exc:
                self.counters.callback_error_count += 1
                self.callback_errors.append(f"{type(exc).__name__}: {exc}")

        return actuate

    def observation_callback(self, api: Any) -> Callable[[Any], None]:
        def observe(state: Any) -> None:
            try:
                exchange = api.exchange
                if (
                    not exchange.api_data_fully_ready(state)
                    or exchange.warmup_flag(state)
                    or int(exchange.kind_of_sim(state)) != self.settings.weather_environment_type
                    or not self._ensure_handles(exchange, state)
                ):
                    return
                clock = self._clock(exchange, state)
                effective = float(exchange.get_variable_value(state, self.setpoint_handle))
                occupancy = float(exchange.get_variable_value(state, self.occupancy_handle))
                self.counters.last_observed_effective_setpoint = effective
                event_type = ActuatorEventType.CONTROL_RUN_OBSERVATION
                if self.reset_complete and self.plan.position(*clock) is WindowPosition.AFTER:
                    event_type = ActuatorEventType.POST_RESET_VERIFIED
                self._emit(event_type, clock, effective=effective, occupancy=occupancy)
            except BaseException as exc:
                self.counters.callback_error_count += 1
                self.callback_errors.append(f"{type(exc).__name__}: {exc}")

        return observe

    def close(self) -> None:
        if (
            self._api is not None
            and self._state is not None
            and self.override_active
            and self.registry.handle is not None
        ):
            self._api.exchange.reset_actuator(self._state, self.registry.handle)
            self.override_active = False
            self.counters.reset_calls += 1
        if self.writer is not None:
            self.writer.close()
        if self.registry.discoveries:
            self.registry.write_discovery(self.output_directory / self.settings.discovery_csv)
        manifest = {
            "approved_actuator_count": 1,
            "approved_actuator": asdict(self.settings.definition),
            "handle": self.registry.handle,
            "discovered_actuator_count": len(self.registry.discoveries),
            "eligible_actuator_count": sum(item.eligible for item in self.registry.discoveries),
            "plan": asdict(self.plan),
        }
        write_json(
            self.output_directory / self.settings.manifest_json,
            manifest,
        )
        if self.callback_errors:
            (self.output_directory / "callback_errors.log").write_text(
                "\n".join(self.callback_errors) + "\n", encoding="utf-8"
            )

    def summary(self) -> dict[str, Any]:
        return {
            **asdict(self.counters),
            "run_type": self.run_type,
            "handle": self.registry.handle,
            "handle_acquisition_attempts": self.registry.acquisition_attempts,
            "registry_api_error_count": self.registry.api_error_count,
            "approved_actuator_count": 1,
            "unapproved_actuator_write_count": 0,
        }
