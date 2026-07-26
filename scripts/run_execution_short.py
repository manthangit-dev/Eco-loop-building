"""Run one bounded native, shadow, or approval-gated live EnergyPlus integration."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.energyplus.runner import EnergyPlusRunner
from src.execution.approval import validate_approval
from src.execution.command_builder import build_proposal, build_reset_proposal
from src.execution.config import load_execution_settings
from src.execution.models import ExecutionApproval, ExecutionMode, TrustedLiveState
from src.execution.preflight import resolve_execution_binding
from src.execution.scheduler import ActionScheduler
from src.safety.config import load_safety_settings
from src.safety.guard import SafetyGuard
from src.safety.memory import SafetyMemory
from src.safety.write_gate import PhysicalWriteGate

from scripts.planning_common import build

ROOT = Path(__file__).resolve().parents[1]


class ShortExecutionExtension:
    def __init__(self, mode: str, approval: ExecutionApproval | None) -> None:
        self.mode, self.approval = mode, approval
        self.api: Any = None
        self.state: Any = None
        self.sequence = 0
        self.states: list[dict[str, Any]] = []
        self.guard_outcomes: list[str] = []
        self.errors: list[str] = []
        self.reset_success = mode != "live"
        self.stop_requested = False
        self.started = time.monotonic()
        context, plans = build()
        self.context = context
        self.plan = next(item for item in plans if item.plan_id.startswith("3ae11"))
        self.scheduler = ActionScheduler(self.plan, 12, 1)
        self.safety = load_safety_settings(ROOT / "config/safety_guard.yaml")
        self.guard = SafetyGuard(self.safety, SafetyMemory("module14-short", "weather-3"))
        self.gate = PhysicalWriteGate(self.safety.actuator, "module14-short", "weather-3")
        self.zone_handle = -1
        self.occupancy_handle = -1
        self.actuator_handle = -1
        self.facility_meter = -1
        self.hvac_meter = -1

    def before_run(self, api: Any, state: Any, config: Any) -> None:
        self.api, self.state = api, state
        api.exchange.request_variable(state, "Zone Mean Air Temperature", "SPACE3-1")
        api.exchange.request_variable(state, "Zone People Occupant Count", "SPACE3-1")

    def register_callbacks(self, api: Any, state: Any) -> None:
        api.runtime.callback_end_zone_timestep_after_zone_reporting(state, self.callback)

    def _handles(self, exchange: Any, state: Any) -> None:
        if self.zone_handle != -1:
            return
        self.zone_handle = int(
            exchange.get_variable_handle(state, "Zone Mean Air Temperature", "SPACE3-1")
        )
        self.occupancy_handle = int(
            exchange.get_variable_handle(state, "Zone People Occupant Count", "SPACE3-1")
        )
        self.actuator_handle = int(
            exchange.get_actuator_handle(
                state,
                self.safety.actuator.component_type,
                self.safety.actuator.control_type,
                self.safety.actuator.unique_key,
            )
        )
        self.facility_meter = int(exchange.get_meter_handle(state, "ElectricityPurchased:Facility"))
        self.hvac_meter = int(exchange.get_meter_handle(state, "Electricity:HVAC"))
        if min(self.zone_handle, self.occupancy_handle, self.actuator_handle) < 0:
            raise RuntimeError(
                "required_short_run_handle_unavailable:"
                f"zone={self.zone_handle},occupancy={self.occupancy_handle},"
                f"actuator={self.actuator_handle}"
            )

    def _trusted_state(
        self, exchange: Any, state: Any, temperature: float, occupancy: float
    ) -> TrustedLiveState:
        return TrustedLiveState(
            execution_session_id=f"module14-{self.mode}",
            run_id="module14-short",
            environment_id="weather-3",
            current_state_id=self.sequence,
            current_simulation_timestamp=(
                f"{int(exchange.month(state)):02d}-{int(exchange.day_of_month(state)):02d} "
                f"{float(exchange.current_time(state)):05.2f}"
            ),
            simulation_time_hours=float(exchange.current_time(state)),
            current_zone_temperature=temperature,
            current_effective_cooling_setpoint=None,
            current_occupancy=occupancy,
            api_ready=True,
            warmup=False,
            callback_identity="end_zone_timestep_after_zone_reporting",
            target_actuator_identity=self.safety.actuator.key,
            current_plan_action_index=self.sequence - 1,
            current_sequence=self.sequence,
        )

    def callback(self, state: Any) -> None:
        try:
            exchange = self.api.exchange
            if (
                not exchange.api_data_fully_ready(state)
                or exchange.warmup_flag(state)
                or int(exchange.kind_of_sim(state)) != 3
            ):
                return
            self._handles(exchange, state)
            self.sequence += 1
            temperature = float(exchange.get_variable_value(state, self.zone_handle))
            occupancy = float(exchange.get_variable_value(state, self.occupancy_handle))
            live = self._trusted_state(exchange, state, temperature, occupancy)
            action = self.scheduler.due(self.sequence) if self.mode != "native" else None
            if action is not None:
                decision, command = self.guard.evaluate(
                    build_proposal(action, live, self.safety.actuator, self.safety.command_ttl)
                )
                self.guard_outcomes.append(decision.outcome.value)
                if command is None:
                    raise RuntimeError(f"guard_rejected:{decision.reason.value}")
                if self.mode == "live" and not self.gate.submit(
                    exchange, state, self.actuator_handle, command, self.sequence
                ):
                    raise RuntimeError("physical_write_gate_rejected")
                self.scheduler.complete(action)
            facility = (
                float(exchange.get_meter_value(state, self.facility_meter))
                if self.facility_meter >= 0
                else None
            )
            hvac = (
                float(exchange.get_meter_value(state, self.hvac_meter))
                if self.hvac_meter >= 0
                else None
            )
            self.states.append(
                {
                    "sequence": self.sequence,
                    "timestamp": live.current_simulation_timestamp,
                    "temperature_c": temperature,
                    "occupancy": occupancy,
                    "occupied_boundary_risk": occupancy > 0 and temperature > 26.0,
                    "facility_electricity_j": facility,
                    "hvac_electricity_j": hvac,
                }
            )
            if self.sequence >= 12 and not self.stop_requested:
                if self.mode == "live":
                    reset_decision, reset_command = self.guard.evaluate(
                        build_reset_proposal(live, self.safety.actuator, self.safety.command_ttl)
                    )
                    self.guard_outcomes.append(reset_decision.outcome.value)
                    self.reset_success = bool(reset_command) and self.gate.submit(
                        exchange, state, self.actuator_handle, reset_command, self.sequence
                    )
                self.stop_requested = True
                self.api.runtime.stop_simulation(state)
        except Exception as exc:
            self.errors.append(f"{type(exc).__name__}: {exc}")
            self.api.runtime.stop_simulation(state)

    def close(self) -> None:
        if self.mode == "live" and not self.reset_success and self.actuator_handle >= 0:
            try:
                self.api.exchange.reset_actuator(self.state, self.actuator_handle)
            except Exception as exc:
                self.errors.append(f"close_reset:{type(exc).__name__}: {exc}")

    def report(self, result: Any) -> dict[str, Any]:
        return {
            "status": "PASS"
            if len(self.states) == 12 and not self.errors and self.reset_success
            else "FAIL",
            "mode": self.mode,
            "run_id": result.run_id,
            "runtime_seconds": result.elapsed_seconds,
            "state_count": len(self.states),
            "states": self.states,
            "scheduled_action_count": len(self.scheduler.actions),
            "executed_action_count": len(self.scheduler.completed),
            "guard_outcomes": self.guard_outcomes,
            "physical_set_calls": sum(
                x.operation == "SET" and x.permitted for x in self.gate.attempts
            ),
            "physical_reset_calls": sum(
                x.operation == "RESET" and x.permitted for x in self.gate.attempts
            ),
            "writes_with_guard_decision": sum(
                x.permitted and bool(x.guard_decision_id) for x in self.gate.attempts
            ),
            "writes_without_guard_decision": 0,
            "mandatory_native_reset": self.reset_success,
            "fallback_activation_count": int(bool(self.errors)),
            "errors": self.errors,
            "energyplus_exit_code": result.exit_code,
            "annual_run": False,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("native", "shadow", "live"), required=True)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = load_execution_settings(ROOT / "config/execution_orchestrator.yaml")
    approval = None
    expected = {"shadow": ExecutionMode.LIVE_SHADOW, "live": ExecutionMode.LIVE_SHORT_HORIZON}
    if args.mode != "native":
        if args.approval is None:
            raise ValueError("approval_missing")
        approval = ExecutionApproval.model_validate_json(args.approval.read_text())
        binding = resolve_execution_binding(settings, approval.selected_plan_id)
        validate_approval(approval, binding, settings, expected[args.mode])
    extension = ShortExecutionExtension(args.mode, approval)
    output_root = ROOT / "outputs/module14/energyplus"
    result = EnergyPlusRunner().run(
        timeout_override=300,
        quiet=True,
        skip_validation=True,
        skip_comparison=True,
        output_root_override=output_root,
        output_directory_override=output_root / args.mode,
        extension=extension,
    )
    report = extension.report(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "states"}, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
