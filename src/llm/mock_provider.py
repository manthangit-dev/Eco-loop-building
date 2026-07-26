"""Scripted deterministic provider used for verification."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.llm.models import LocalModel, ProviderMessage, ProviderOutput


class DeterministicMockProvider:
    name = "deterministic_mock"
    model = "module10-v1-fixture"

    def __init__(self, outputs: Sequence[ProviderOutput]) -> None:
        self.outputs = list(outputs)
        self.index = 0
        self.cancelled = False
        self.closed = False

    def health_check(self) -> bool:
        return not self.closed

    def list_local_models(self) -> tuple[LocalModel, ...]:
        return (LocalModel(name=self.model),)

    def generate(self, messages: Sequence[ProviderMessage]) -> ProviderOutput:
        return self.generate_with_tools(messages, ())

    def generate_with_tools(
        self, messages: Sequence[ProviderMessage], tools: Sequence[dict[str, Any]]
    ) -> ProviderOutput:
        if self.cancelled:
            raise RuntimeError("provider_cancelled")
        if self.index >= len(self.outputs):
            raise RuntimeError("empty_provider_response")
        output = self.outputs[self.index]
        self.index += 1
        return output

    def count_or_estimate_tokens(self, text: str) -> int:
        return (len(text) + 3) // 4

    def cancel(self) -> None:
        self.cancelled = True

    def close(self) -> None:
        self.closed = True
