from typing import Any

from src.control.command_buffer import LatestCommandBuffer
from src.control.fallback_executor import FallbackExecutor

from tests.control_helpers import settings


class Exchange:
    def api_data_fully_ready(self, _state: Any) -> bool:
        return True

    def warmup_flag(self, _state: Any) -> bool:
        return False

    def kind_of_sim(self, _state: Any) -> int:
        return 3

    def get_actuator_handle(self, *_args: Any) -> int:
        return 7

    def reset_actuator(self, *_args: Any) -> None:
        return

    def set_actuator_value(self, *_args: Any) -> None:
        return


class Runtime:
    def callback_after_predictor_before_hvac_managers(self, _state: Any, callback: Any) -> None:
        self.callback = callback


class API:
    def __init__(self) -> None:
        self.exchange = Exchange()
        self.runtime = Runtime()


def test_executor_skips_without_command_and_acquires_only_approved_handle() -> None:
    executor = FallbackExecutor(settings(), LatestCommandBuffer(settings().actuator))
    api = API()
    executor.before_run(api, object(), object())
    executor.register_callbacks(api, object())
    api.runtime.callback(object())
    assert executor.handle == 7 and executor.set_calls == 0


def test_executor_contains_api_exception() -> None:
    executor = FallbackExecutor(settings(), LatestCommandBuffer(settings().actuator))
    api = API()
    api.exchange.api_data_fully_ready = lambda _state: (_ for _ in ()).throw(RuntimeError("api"))  # type: ignore[method-assign]
    executor.register_callbacks(api, object())
    api.runtime.callback(object())
    assert len(executor.callback_errors) == 1
