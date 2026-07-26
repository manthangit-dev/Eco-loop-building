"""Strict native and JSON-fallback tool call parsing."""

from __future__ import annotations

import json
import math

from pydantic import TypeAdapter

from src.llm.models import ModelToolCall, ProviderOutput


def _safe(value: object, depth: int = 0) -> None:
    if depth > 8:
        raise ValueError("arguments too deeply nested")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite argument")
    if isinstance(value, bool):
        return
    if isinstance(value, str) and len(value) > 2000:
        raise ValueError("argument string too long")
    if isinstance(value, list):
        if len(value) > 100:
            raise ValueError("argument list too long")
        for item in value:
            _safe(item, depth + 1)
    if isinstance(value, dict):
        for item in value.values():
            _safe(item, depth + 1)


def parse_tool_call(output: ProviderOutput) -> ModelToolCall | None:
    call = output.tool_call
    if call is None and output.text.strip().startswith("{"):
        payload = json.loads(output.text)
        if "tool_call" in payload:
            call = TypeAdapter(ModelToolCall).validate_python(payload["tool_call"])
    if call is not None:
        _safe(call.arguments)
    return call
