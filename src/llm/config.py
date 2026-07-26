"""Strict local LLM supervisor configuration."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from urllib.parse import urlparse

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, model_validator


class LLMSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    root: Path
    schema_version: int = 1
    enabled: bool
    provider: str
    endpoint: str
    selected_model: str | None
    context_capacity: int = Field(gt=0, le=131072)
    maximum_input_tokens: int = Field(gt=0)
    maximum_output_tokens: int = Field(gt=0)
    maximum_supervisor_iterations: int = Field(gt=0, le=12)
    maximum_tool_calls: int = Field(gt=0, le=8)
    maximum_repeated_tool_calls: int = Field(gt=0, le=2)
    maximum_correction_attempts: int = Field(ge=0, le=2)
    temperature: float = Field(ge=0, le=1)
    mock_fixture: str
    provider_timeout_seconds: int = Field(gt=0, le=300)
    tool_timeout_seconds: int = Field(gt=0, le=60)
    session_timeout_seconds: int = Field(gt=0, le=600)
    maximum_tool_result_characters: int = Field(gt=0, le=50000)
    maximum_conversation_messages: int = Field(gt=2, le=50)
    retry_limit: int = Field(ge=0, le=1)
    prompt_template_version: int = 1
    supervisor_schema_version: int = 1
    allowed_classifications: tuple[str, ...]
    denied_tools: tuple[str, ...]
    local_only: bool
    redact_fields: tuple[str, ...]
    dry_run_only: bool
    fail_closed: bool
    model_acquisition_limit_gb: int = Field(ge=0, le=1)
    database: Path
    output_root: Path

    @model_validator(mode="after")
    def safe(self) -> LLMSettings:
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "http" or parsed.hostname is None:
            raise ValueError("local provider requires an http loopback endpoint")
        try:
            loopback = ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            loopback = parsed.hostname.lower() == "localhost"
        if not loopback or not self.local_only or not self.dry_run_only:
            raise ValueError("remote or physical LLM operation is forbidden")
        if self.provider not in {"local_ollama", "deterministic_mock"}:
            raise ValueError("unsupported provider")
        if self.maximum_input_tokens + self.maximum_output_tokens > self.context_capacity:
            raise ValueError("token budget exceeds context capacity")
        return self


def load_llm_settings(path: Path) -> LLMSettings:
    root = path.resolve().parents[1]
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    values = {**raw["llm"], **raw["storage"], "root": root}
    values["database"] = root / values["database"]
    values["output_root"] = root / values["output_root"]
    return LLMSettings.model_validate(values)
