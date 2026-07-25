"""Exception-contained end-of-zone-timestep sensor collection."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

from src.energyplus.run_config import RunnerConfig
from src.energyplus.sensor_definitions import ExchangeKind, SensorSettings
from src.energyplus.sensor_registry import SensorRegistry
from src.energyplus.sensor_snapshot import (
    BuildingSensorState,
    OutdoorSensorState,
    SensorSnapshot,
    SimulationTimestamp,
    ZoneSensorState,
)
from src.energyplus.sensor_writers import SensorWriters


@dataclass
class CollectorCounters:
    total_callback_invocations: int = 0
    calls_before_data_readiness: int = 0
    warmup_calls_skipped: int = 0
    non_weather_environments_skipped: int = 0
    successful_snapshots: int = 0
    duplicate_snapshots_rejected: int = 0
    sensor_read_errors: int = 0
    api_error_flag_activations: int = 0
    missing_required_handles: int = 0
    missing_optional_handles: int = 0
    writer_errors: int = 0
    first_snapshot_time: str = ""
    last_snapshot_time: str = ""


class SensorCollector:
    def __init__(self, settings: SensorSettings) -> None:
        self.settings = settings
        self.registry = SensorRegistry(settings, settings.output_directory)
        self.writers: SensorWriters | None = None
        self.counters = CollectorCounters()
        self.callback_errors: list[str] = []
        self._seen: set[tuple[int, int, int, int, int]] = set()
        self._last_sim_time: float | None = None
        self._reference: Callable[[Any], None] | None = None

    def before_run(self, api: Any, state: Any, _config: RunnerConfig) -> None:
        optional_meter_ids = tuple(
            definition.logical_id
            for definition in self.settings.definitions
            if definition.exchange_kind is ExchangeKind.METER
            and not definition.required
        )
        self.writers = SensorWriters(
            self.settings.output_directory,
            self.settings.output_root,
            self.settings.snapshots_jsonl,
            self.settings.snapshots_csv,
            self.settings.zones,
            optional_meter_ids,
            self.settings.flush_every_snapshots,
        )
        self.registry.request_variables(api.exchange, state)

    def register_callbacks(self, api: Any, state: Any) -> None:
        self._reference = self.callback(api)
        api.runtime.callback_end_zone_timestep_after_zone_reporting(
            state, self._reference
        )

    def _timestamp(self, exchange: Any, state: Any) -> SimulationTimestamp:
        return SimulationTimestamp(
            environment_number=int(exchange.current_environment_num(state)),
            environment_type=int(exchange.kind_of_sim(state)),
            year=int(exchange.year(state)),
            calendar_year=int(exchange.calendar_year(state)),
            month=int(exchange.month(state)),
            day=int(exchange.day_of_month(state)),
            day_of_year=int(exchange.day_of_year(state)),
            day_of_week=int(exchange.day_of_week(state)),
            hour=int(exchange.hour(state)),
            minute=int(exchange.minutes(state)),
            current_time=float(exchange.current_time(state)),
            current_simulation_time=float(exchange.current_sim_time(state)),
            zone_timestep_number=int(exchange.zone_time_step_number(state)),
            timesteps_per_hour=int(exchange.num_time_steps_in_hour(state)),
            warmup=bool(exchange.warmup_flag(state)),
        )

    def _required(self, exchange: Any, state: Any, logical_id: str) -> float:
        value = self.registry.read(exchange, state, logical_id)
        if value is None or not math.isfinite(value):
            raise RuntimeError(f"Required sensor is unavailable or non-finite: {logical_id}")
        return value

    def _optional(self, exchange: Any, state: Any, logical_id: str) -> float | None:
        try:
            value = self.registry.read(exchange, state, logical_id)
            return value if value is None or math.isfinite(value) else None
        except RuntimeError as exc:
            self.callback_errors.append(f"Optional sensor {logical_id}: {exc}")
            self.counters.sensor_read_errors += 1
            return None

    def _build_snapshot(
        self, exchange: Any, state: Any, timestamp: SimulationTimestamp
    ) -> SensorSnapshot:
        zones = tuple(
            ZoneSensorState(
                zone_name=zone,
                mean_air_temperature_c=self._required(
                    exchange, state, f"zone_mean_air_temperature.{zone}"
                ),
                occupant_count=self._required(
                    exchange, state, f"zone_occupant_count.{zone}"
                ),
                relative_humidity_percent=self._optional(
                    exchange, state, f"zone_relative_humidity.{zone}"
                ),
            )
            for zone in self.settings.zones
        )
        optional_meters = {
            definition.logical_id: self._optional(
                exchange, state, definition.logical_id
            )
            for definition in self.settings.definitions
            if definition.exchange_kind is ExchangeKind.METER
            and not definition.required
        }
        availability = {
            definition.logical_id: self.registry.handle_for(definition.logical_id)
            is not None
            for definition in self.settings.definitions
            if not definition.required
        }
        return SensorSnapshot(
            sequence=self.counters.successful_snapshots + 1,
            timestamp=timestamp,
            outdoor=OutdoorSensorState(
                dry_bulb_c=self._required(exchange, state, "outdoor_dry_bulb"),
                relative_humidity_percent=self._required(
                    exchange, state, "outdoor_relative_humidity"
                ),
            ),
            building=BuildingSensorState(
                facility_electricity_raw_j=self._required(
                    exchange, state, "facility_electricity"
                ),
                facility_demand_rate_w=self._required(
                    exchange, state, "facility_demand_rate"
                ),
                hvac_electricity_raw_j=self._required(
                    exchange, state, "hvac_electricity"
                ),
                optional_meters_raw_j=optional_meters,
            ),
            zones=zones,
            optional_availability=availability,
        )

    @staticmethod
    def _label(timestamp: SimulationTimestamp) -> str:
        return (
            f"env={timestamp.environment_number};day={timestamp.day_of_year};"
            f"{timestamp.hour:02d}:{timestamp.minute:02d};"
            f"step={timestamp.zone_timestep_number}"
        )

    def callback(self, api: Any) -> Callable[[Any], None]:
        def collect(state: Any) -> None:
            try:
                self.counters.total_callback_invocations += 1
                exchange = api.exchange
                if not exchange.api_data_fully_ready(state):
                    self.counters.calls_before_data_readiness += 1
                    return
                if exchange.warmup_flag(state):
                    self.counters.warmup_calls_skipped += 1
                    return
                environment_type = int(exchange.kind_of_sim(state))
                if environment_type != self.settings.weather_run_environment_type:
                    self.counters.non_weather_environments_skipped += 1
                    return
                if not self.registry.initialized:
                    ready = self.registry.initialize(exchange, state)
                    self.registry.capture_available_data(exchange, state)
                    self.counters.api_error_flag_activations = (
                        self.registry.api_error_count
                    )
                    self.counters.missing_required_handles = sum(
                        not item.available and item.required
                        for item in self.registry.discoveries
                    )
                    self.counters.missing_optional_handles = sum(
                        not item.available and not item.required
                        for item in self.registry.discoveries
                    )
                    if not ready:
                        return
                timestamp = self._timestamp(exchange, state)
                identity = timestamp.identity()
                if identity in self._seen:
                    self.counters.duplicate_snapshots_rejected += 1
                    return
                if (
                    self._last_sim_time is not None
                    and timestamp.current_simulation_time < self._last_sim_time
                ):
                    raise RuntimeError("Simulation time moved backwards.")
                snapshot = self._build_snapshot(exchange, state, timestamp)
                if self.writers is None:
                    raise RuntimeError("Sensor writers were not initialized.")
                self.writers.write(snapshot)
                self._seen.add(identity)
                self._last_sim_time = timestamp.current_simulation_time
                self.counters.successful_snapshots += 1
                label = self._label(timestamp)
                if not self.counters.first_snapshot_time:
                    self.counters.first_snapshot_time = label
                self.counters.last_snapshot_time = label
                self.counters.api_error_flag_activations = self.registry.api_error_count
            except BaseException as exc:
                self.callback_errors.append(
                    f"{type(exc).__name__}: {exc}"
                )
                self.counters.sensor_read_errors += 1

        return collect

    def close(self) -> None:
        if self.writers is not None:
            self.writers.close()
        self.registry.write_manifest()
        if self.callback_errors:
            (self.settings.output_directory / "sensor_callback_errors.log").write_text(
                "\n".join(self.callback_errors) + "\n", encoding="utf-8"
            )

    def summary(self) -> dict[str, Any]:
        return {
            **asdict(self.counters),
            "callback_error_count": len(self.callback_errors),
            "registry_api_error_count": self.registry.api_error_count,
            "required_handles_ready": self.registry.required_ready,
            "available_api_data_captured": self.registry.available_data_captured,
            "actuator_access_count": 0,
        }
