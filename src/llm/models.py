"""Typed provider messages and outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProviderMessage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    role: str
    content: str = Field(max_length=50000)


class ModelToolCall(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(max_length=128)
    arguments: dict[str, Any]


class ProviderOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str = Field(default="", max_length=50000)
    tool_call: ModelToolCall | None = None
    finish_reason: str = "stop"


class LocalModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    size: int | None = None
    compatible: bool = True
