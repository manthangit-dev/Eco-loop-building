"""Single-approved-actuator executor; policy never runs here."""

from __future__ import annotations

from typing import Any

from src.control.command_buffer import LatestCommandBuffer
from src.control.config import FallbackSettings


class FallbackExecutor:
    def __init__(self, settings: FallbackSettings, buffer: LatestCommandBuffer) -> None:
        self.settings = settings
        self.buffer = buffer
        self.handle = -1
        self.set_calls = 0
        self.reset_count = 0
        self.expiry_count = 0
        self.api_errors = 0
        self.callback_errors: list[str] = []
        self.current_sequence = 0
        self.active = False
        self.events: list[dict[str, Any]] = []
        self._api: Any = None
        self._state: Any = None

    def before_run(self, _api: Any, _state: Any, _config: Any) -> None:
        self._api, self._state = _api, _state

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
                if command is None or command.reset_required:
                    if self.active:
                        exchange.reset_actuator(state, self.handle)
                        self.reset_count += 1
                        self.active = False
                        self.events.append(
                            {"type": "RESET", "sequence": self.current_sequence, "command_id": None}
                        )
                    return
                if command.shadow_mode:
                    return
                if command.setpoint_celsius is None:
                    raise ValueError("Apply command has no setpoint.")
                exchange.set_actuator_value(state, self.handle, command.setpoint_celsius)
                self.set_calls += 1
                self.active = True
                self.events.append(
                    {
                        "type": "SET",
                        "sequence": self.current_sequence,
                        "command_id": command.command_id,
                        "value": command.setpoint_celsius,
                    }
                )
            except BaseException as exc:
                self.callback_errors.append(f"{type(exc).__name__}: {exc}")

        return callback

    def close(self) -> None:
        if self.active and self.handle >= 0 and self._api is not None:
            try:
                self._api.exchange.reset_actuator(self._state, self.handle)
                self.reset_count += 1
                self.events.append(
                    {"type": "RESET", "sequence": self.current_sequence, "command_id": None}
                )
                self.active = False
            except BaseException as exc:
                self.callback_errors.append(f"cleanup {type(exc).__name__}: {exc}")
        self.buffer.shutdown()
