"""Loopback-only Ollama adapter with no cloud fallback."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any

from src.llm.config import LLMSettings
from src.llm.models import LocalModel, ModelToolCall, ProviderMessage, ProviderOutput


class LocalOpenSourceProvider:
    name = "local_ollama"

    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings
        self.model = settings.selected_model or ""
        self.cancelled = False
        self.closed = False

    def _request(self, route: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.cancelled or self.closed:
            raise RuntimeError("provider unavailable")
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
        request = urllib.request.Request(
            self.settings.endpoint + route,
            data=body,
            headers={"Content-Type": "application/json", "Proxy-Authorization": ""},
            method="GET" if body is None else "POST",
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=self.settings.provider_timeout_seconds) as response:
            raw = response.read(self.settings.maximum_tool_result_characters + 1)
        if len(raw) > self.settings.maximum_tool_result_characters:
            raise ValueError("local model response exceeds configured bound")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("malformed local runtime response")
        return result

    def health_check(self) -> bool:
        try:
            self._request("/api/tags")
        except (OSError, ValueError, urllib.error.URLError):
            return False
        return True

    def list_local_models(self) -> tuple[LocalModel, ...]:
        result = self._request("/api/tags")
        return tuple(
            LocalModel(name=str(item["name"]), size=item.get("size"))
            for item in result.get("models", [])
            if isinstance(item, dict) and item.get("name")
        )

    def generate(self, messages: Sequence[ProviderMessage]) -> ProviderOutput:
        return self.generate_with_tools(messages, ())

    def generate_with_tools(
        self, messages: Sequence[ProviderMessage], tools: Sequence[dict[str, Any]]
    ) -> ProviderOutput:
        if not self.model:
            raise RuntimeError("no local model selected")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [item.model_dump() for item in messages],
            "stream": False,
            "think": False,
            "options": {
                "temperature": self.settings.temperature,
                "num_predict": self.settings.maximum_output_tokens,
            },
        }
        if tools:
            payload["tools"] = list(tools)
        result = self._request("/api/chat", payload)
        message = result.get("message", {})
        calls = message.get("tool_calls", []) if isinstance(message, dict) else []
        call = None
        if calls:
            function = calls[0].get("function", {})
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            call = ModelToolCall(name=function["name"], arguments=arguments)
        return ProviderOutput(text=str(message.get("content", "")), tool_call=call)

    def count_or_estimate_tokens(self, text: str) -> int:
        return (len(text) + 3) // 4

    def cancel(self) -> None:
        self.cancelled = True

    def close(self) -> None:
        self.closed = True
