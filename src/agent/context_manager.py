"""Deterministic bounded context and summaries."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from src.llm.models import ProviderMessage


def estimate_tokens(text: str) -> int:
    return (len(text) + 3) // 4


def summarise_tool_result(data: Any, maximum_characters: int) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str)
    if len(raw) <= maximum_characters:
        return raw
    if isinstance(data, list):
        bounded = {"count": len(data), "first": data[0] if data else None, "truncated": True}
    elif isinstance(data, dict):
        bounded = {"keys": sorted(data), "truncated": True}
    else:
        bounded = {"type": type(data).__name__, "truncated": True}
    return json.dumps(bounded, sort_keys=True, separators=(",", ":"), default=str)


def enforce_budget(
    messages: Sequence[ProviderMessage], maximum_input_tokens: int
) -> tuple[ProviderMessage, ...]:
    selected = list(messages)
    while sum(estimate_tokens(item.content) for item in selected) > maximum_input_tokens:
        removable = next(
            (index for index, item in enumerate(selected) if item.role == "tool"), None
        )
        if removable is None:
            raise ValueError("context_budget_exceeded")
        selected.pop(removable)
    return tuple(selected)
