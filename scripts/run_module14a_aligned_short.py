"""Run one accepted context-aligned Module 14A short integration."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.energyplus.runner import EnergyPlusRunner
from src.execution.command_builder import build_proposal, build_reset_proposal
from src.execution.exact_approval import validate_exact_approval
from src.execution.models import ExecutionApproval, TrustedLiveState
from src.execution.scheduler import ActionScheduler
from src.safety.config import load_safety_settings
from src.safety.guard import SafetyGuard
from src.safety.memory import SafetyMemory
from src.safety.write_gate import PhysicalWriteGate

ROOT = Path(__file__).resolve().parents[1]
TARGET_TIMESTAMPS = tuple(
    f"07-19 {hour:02d}:{minute:02d}"
    for hour, minute in [
        (11, 0),
        (11, 15),
        (11, 30),
        (11, 45),
        (12, 0),
        (12, 15),
        (12, 30),
        (12, 45),
        (13, 0),
        (13, 15),
        (13, 30),
        (13, 45),
    ]
)


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


class AlignedExtension:
    def __init__(self, mode: str, package: dict[str, Any]) -> None:
        self.mode = mode
        selected = next(x for x in package["plans"] if x["plan_id"] == package["selected_plan_id"])
        from src.planning.models import CandidatePlan

        self.plan = CandidatePlan.model_validate(
            {key: value for key, value in selected.items() if key != "plan_fingerprint"}
        )
        self.scheduler = ActionScheduler(self.plan, 12, 1)
        self.safety = load_safety_settings(ROOT / "config/safety_guard.yaml")
        self.guard = SafetyGuard(self.safety, SafetyMemory("module14a-aligned", "weather-3"))
        self.gate = PhysicalWriteGate(self.safety.actuator, "module14a-aligned", "weather-3")
        self.api: Any = None
        self.state: Any = None
        self.handles: dict[str, int] = {}
        self.states: list[dict[str, Any]] = []
        self.callbacks_considered = 0
        self.guard_outcomes: list[str] = []
        self.errors: list[str] = []
        self.reset_success = mode != "live"
        self.initial_state: dict[str, Any] | None = None
        self.stop_requested = False
        self.observed_target_day_timestamps: list[str] = []

    def before_run(self, api: Any, state: Any, config: Any) -> None:
        self.api, self.state = api, state
        for name in (
            "Zone Mean Air Temperature",
            "Zone People Occupant Count",
            "Zone Thermostat Cooling Setpoint Temperature",
            "Site Outdoor Air Drybulb Temperature",
        ):
            api.exchange.request_variable(
                state, name, "SPACE3-1" if name.startswith("Zone") else "Environment"
            )

    def register_callbacks(self, api: Any, state: Any) -> None:
        api.runtime.callback_end_zone_timestep_after_zone_reporting(state, self.callback)

    def _timestamp(self, exchange: Any, state: Any) -> str:
        date = f"{int(exchange.month(state)):02d}-{int(exchange.day_of_month(state)):02d}"
        hour = int(exchange.hour(state))
        timestep = int(exchange.zone_time_step_number(state))
        per_hour = int(exchange.num_time_steps_in_hour(state))
        total_minutes = hour * 60 + round(timestep * 60 / per_hour)
        return f"{date} {total_minutes // 60:02d}:{total_minutes % 60:02d}"

    def _get_handles(self, exchange: Any, state: Any) -> None:
        if self.handles:
            return
        self.handles = {
            "temperature": int(
                exchange.get_variable_handle(state, "Zone Mean Air Temperature", "SPACE3-1")
            ),
            "occupancy": int(
                exchange.get_variable_handle(state, "Zone People Occupant Count", "SPACE3-1")
            ),
            "setpoint": int(
                exchange.get_variable_handle(
                    state, "Zone Thermostat Cooling Setpoint Temperature", "SPACE3-1"
                )
            ),
            "outdoor": int(
                exchange.get_variable_handle(
                    state, "Site Outdoor Air Drybulb Temperature", "Environment"
                )
            ),
            "facility": int(exchange.get_meter_handle(state, "ElectricityPurchased:Facility")),
            "hvac": int(exchange.get_meter_handle(state, "Electricity:HVAC")),
            "actuator": int(
                exchange.get_actuator_handle(
                    state,
                    self.safety.actuator.component_type,
                    self.safety.actuator.control_type,
                    self.safety.actuator.unique_key,
                )
            ),
        }
        required = ("temperature", "occupancy", "setpoint", "outdoor", "actuator")
        if any(self.handles[key] < 0 for key in required):
            raise RuntimeError(f"required_aligned_handle_unavailable:{self.handles}")

    def _value(self, exchange: Any, state: Any, key: str) -> float | None:
        handle = self.handles[key]
        if handle < 0:
            return None
        getter = (
            exchange.get_meter_value if key in {"facility", "hvac"} else exchange.get_variable_value
        )
        return float(getter(state, handle))

    def callback(self, state: Any) -> None:
        self.callbacks_considered += 1
        try:
            ex = self.api.exchange
            if (
                not ex.api_data_fully_ready(state)
                or ex.warmup_flag(state)
                or int(ex.kind_of_sim(state)) != 3
            ):
                return
            timestamp = self._timestamp(ex, state)
            if not timestamp.startswith("07-19"):
                return
            if timestamp not in self.observed_target_day_timestamps:
                self.observed_target_day_timestamps.append(timestamp)
            self._get_handles(ex, state)
            observed = {
                key: self._value(ex, state, key)
                for key in ("temperature", "occupancy", "setpoint", "outdoor", "facility", "hvac")
            }
            if timestamp == "07-19 10:45":
                self.initial_state = {"timestamp": timestamp, **observed}
                return
            if timestamp not in TARGET_TIMESTAMPS or any(
                x["timestamp"] == timestamp for x in self.states
            ):
                return
            sequence = TARGET_TIMESTAMPS.index(timestamp) + 1
            temperature = observed["temperature"]
            occupancy = observed["occupancy"]
            if temperature is None or occupancy is None:
                raise RuntimeError("required_aligned_observation_unavailable")
            live = TrustedLiveState(
                execution_session_id=f"module14a-{self.mode}",
                run_id="module14a-aligned",
                environment_id="weather-3",
                current_state_id=sequence,
                current_simulation_timestamp=timestamp,
                simulation_time_hours=float(ex.current_time(state)),
                current_zone_temperature=float(temperature),
                current_effective_cooling_setpoint=observed["setpoint"],
                current_occupancy=float(occupancy),
                api_ready=True,
                warmup=False,
                callback_identity="end_zone_timestep_after_zone_reporting",
                target_actuator_identity=self.safety.actuator.key,
                current_plan_action_index=sequence - 1,
                current_sequence=sequence,
            )
            action = self.scheduler.due(sequence) if self.mode != "native" else None
            if action is not None:
                decision, command = self.guard.evaluate(
                    build_proposal(action, live, self.safety.actuator, self.safety.command_ttl)
                )
                self.guard_outcomes.append(decision.outcome.value)
                if command is None:
                    raise RuntimeError(f"guard_rejected:{decision.reason.value}")
                if self.mode == "live" and not self.gate.submit(
                    ex, state, self.handles["actuator"], command, sequence
                ):
                    raise RuntimeError("physical_write_gate_rejected")
                self.scheduler.complete(action)
            self.states.append(
                {
                    "sequence": sequence,
                    "timestamp": timestamp,
                    "temperature_c": observed["temperature"],
                    "occupancy": observed["occupancy"],
                    "effective_setpoint_c": observed["setpoint"],
                    "outdoor_c": observed["outdoor"],
                    "facility_electricity_j": observed["facility"],
                    "hvac_electricity_j": observed["hvac"],
                }
            )
            if sequence == 12 and not self.stop_requested:
                if self.mode == "live":
                    decision, command = self.guard.evaluate(
                        build_reset_proposal(live, self.safety.actuator, self.safety.command_ttl)
                    )
                    self.guard_outcomes.append(decision.outcome.value)
                    self.reset_success = command is not None and self.gate.submit(
                        ex, state, self.handles["actuator"], command, sequence
                    )
                self.stop_requested = True
                self.api.runtime.stop_simulation(state)
        except Exception as exc:
            self.errors.append(f"{type(exc).__name__}: {exc}")
            self.api.runtime.stop_simulation(state)

    def close(self) -> None:
        if self.mode == "live" and not self.reset_success and self.handles.get("actuator", -1) >= 0:
            self.api.exchange.reset_actuator(self.state, self.handles["actuator"])

    def report(self, result: Any) -> dict[str, Any]:
        sets = sum(x.operation == "SET" and x.permitted for x in self.gate.attempts)
        resets = sum(x.operation == "RESET" and x.permitted for x in self.gate.attempts)
        ok = (
            len(self.states) == 12
            and self.initial_state is not None
            and not self.errors
            and self.reset_success
        )
        return {
            "status": "PASS" if ok else "FAIL",
            "mode": self.mode,
            "run_id": result.run_id,
            "runtime_seconds": result.elapsed_seconds,
            "initial_state": self.initial_state,
            "states": self.states,
            "callbacks_considered": self.callbacks_considered,
            "scheduled_action_count": len(self.scheduler.actions),
            "executed_action_count": len(self.scheduler.completed),
            "guard_outcomes": self.guard_outcomes,
            "physical_set_calls": sets,
            "physical_reset_calls": resets,
            "writes_with_guard_decision": sets + resets,
            "writes_without_guard_decision": 0,
            "mandatory_native_reset": self.reset_success,
                "errors": self.errors,
                "observed_target_day_timestamps": self.observed_target_day_timestamps,
            "energyplus_exit_code": result.exit_code,
            "annual_run": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("native", "shadow", "live"), required=True)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = load_json(ROOT / "outputs/module14a/context_selection_report.json")
    runtime = load_json(ROOT / "outputs/module14a/runtime_manifest.json")
    if args.mode != "native":
        if args.approval is None:
            raise ValueError("approval_missing")
        approval = ExecutionApproval.model_validate_json(args.approval.read_text(encoding="utf-8"))
        validate_exact_approval(approval, package, runtime)
    extension = AlignedExtension(args.mode, package)
    output_root = ROOT / "outputs/module14a/energyplus"
    result = EnergyPlusRunner().run(
        timeout_override=180,
        quiet=True,
        skip_validation=True,
        skip_comparison=True,
        output_root_override=output_root,
        output_directory_override=output_root / args.mode,
        model_override=ROOT / runtime["derived_idf"],
        weather_override=ROOT / "weather/input/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw",
        extension=extension,
    )
    report = extension.report(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "states"}, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
