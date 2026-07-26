"""EnergyPlus executor whose input type is exclusively GuardedCommand."""

from __future__ import annotations

from typing import Any

from src.control.config import FallbackSettings
from src.safety.guard import SafetyGuard
from src.safety.models import ProposedCommand
from src.safety.write_gate import GuardedCommandBuffer, PhysicalWriteGate


class SafetyExecutor:
    def __init__(
        self, settings: FallbackSettings, buffer: GuardedCommandBuffer, gate: PhysicalWriteGate
    ) -> None:
        self.settings, self.buffer, self.gate = settings, buffer, gate
        self.handle = -1
        self.set_calls = self.reset_count = self.expiry_count = self.api_errors = 0
        self.callback_errors: list[str] = []
        self.current_sequence = 0
        self.active = False
        self.events: list[dict[str, Any]] = []
        self._api: Any = None
        self._state: Any = None
        self.guard: SafetyGuard | None = None

    def before_run(self, api: Any, state: Any, _config: Any) -> None:
        self._api, self._state = api, state

    def register_callbacks(self, api: Any, state: Any) -> None:
        api.runtime.callback_after_predictor_before_hvac_managers(state, self._callback(api, state))

    def _callback(self, api: Any, state: Any) -> Any:
        def callback(_state: Any) -> None:
            try:
                exchange = api.exchange
                if not exchange.api_data_fully_ready(state) or exchange.warmup_flag(state):
                    return
                if int(exchange.kind_of_sim(state)) != 3:
                    return
                if self.handle < 0:
                    self.handle = int(
                        exchange.get_actuator_handle(
                            state,
                            self.settings.actuator.component_type,
                            self.settings.actuator.control_type,
                            self.settings.actuator.unique_key,
                        )
                    )
                    if self.handle < 0:
                        self.api_errors += 1
                        return
                command = self.buffer.latest(self.current_sequence)
                if command is None:
                    return
                before = len(self.gate.attempts)
                submitted = self.gate.submit(
                    exchange, state, self.handle, command, self.current_sequence
                )
                if not submitted:
                    return
                attempt = self.gate.attempts[-1]
                if attempt.operation == "RESET":
                    self.reset_count += 1
                    self.active = False
                else:
                    self.set_calls += 1
                    self.active = True
                if len(self.gate.attempts) > before:
                    self.events.append(
                        {
                            "type": attempt.operation,
                            "sequence": self.current_sequence,
                            "command_id": attempt.command_id,
                            "guard_decision_id": attempt.guard_decision_id,
                            "value": attempt.value,
                        }
                    )
            except Exception as exc:
                self.callback_errors.append(f"{type(exc).__name__}: {exc}")

        return callback

    def close(self) -> None:
        if self.active and self.handle >= 0 and self._api is not None:
            try:
                if self.guard is not None:
                    source = self.current_sequence - 1
                    proposal = ProposedCommand(
                        "module8-shutdown-reset", "module8-shutdown",
                        self.gate.run_id, self.gate.environment_id,
                        self.settings.real_zone, self.settings.actuator, None,
                        source, source, self.current_sequence,
                        self.current_sequence + 1, self.current_sequence,
                        source / 4.0, source / 4.0, self.current_sequence / 4.0,
                        reset_required=True,
                    )
                    _decision, guarded_reset = self.guard.evaluate(proposal)
                    if guarded_reset is not None:
                        self.buffer.publish(guarded_reset)
                command = self.buffer.latest(self.current_sequence)
                if command is not None and self.gate.submit(
                    self._api.exchange, self._state, self.handle, command,
                    self.current_sequence,
                ):
                    attempt = self.gate.attempts[-1]
                    self.reset_count += int(attempt.operation == "RESET")
                    self.events.append({"type": attempt.operation,
                        "sequence": self.current_sequence, "command_id": attempt.command_id,
                        "guard_decision_id": attempt.guard_decision_id,
                        "value": attempt.value})
                    self.active = False
            except Exception as exc:
                self.callback_errors.append(f"cleanup {type(exc).__name__}: {exc}")
        self.buffer.shutdown()
