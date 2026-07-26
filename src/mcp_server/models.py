"""Typed MCP request, response, registry, and error models."""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ToolClassification(StrEnum):
    READ_ONLY = "READ_ONLY"
    PROPOSAL_ONLY = "PROPOSAL_ONLY"
    CONTROL_CAPABLE = "CONTROL_CAPABLE"


class ToolError(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    code: str
    message: str
    field: str | None = None


class ToolRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request_id: str = Field(min_length=1, max_length=128)
    tool_name: str = Field(min_length=1, max_length=128)
    arguments: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 1


class ToolEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    request_id: str
    tool_call_id: str
    tool_name: str
    tool_schema_version: int
    success: bool
    data: Any = None
    errors: tuple[ToolError, ...] = ()
    warnings: tuple[str, ...] = ()
    run_id: str | None = None
    environment_id: str | None = None
    source_timestamp: str | None = None
    processing_metadata: str = "deterministic_recorded_artifact"
    truncated: bool = False
    next_cursor: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str


class ToolDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    purpose: str
    classification: ToolClassification
    enabled: bool
    schema_version: int = 1
    maximum_results: int = 100


class ControlProposalInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    run_id: str
    environment_id: str
    source_state_sequence: int = Field(gt=0)
    current_sequence: int = Field(gt=0)
    decision_sequence: int | None = Field(default=None, gt=0)
    valid_from_sequence: int | None = Field(default=None, gt=0)
    expires_after_sequence: int | None = Field(default=None, gt=0)
    component_type: str
    control_type: str
    actuator_key: str
    zone: str
    units: str
    requested_value: float
    client_request_id: str
    rationale: str | None = Field(default=None, max_length=500)

    @field_validator("requested_value", mode="before")
    @classmethod
    def finite_number(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("requested_value must be numeric and not boolean")
        if not math.isfinite(float(value)):
            raise ValueError("requested_value must be finite")
        return value


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    )


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()
