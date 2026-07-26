"""Typed dashboard evidence models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field

from src.planning.provenance import planning_fingerprint


class ClaimClassification(StrEnum):
    VERIFIED_REPOSITORY_FACT = "VERIFIED_REPOSITORY_FACT"
    QUALIFIED_MODEL_RESULT = "QUALIFIED_MODEL_RESULT"
    SHORT_HORIZON_SIMULATION_RESULT = "SHORT_HORIZON_SIMULATION_RESULT"
    ADVISORY_PROXY = "ADVISORY_PROXY"
    SCENARIO_ASSUMPTION = "SCENARIO_ASSUMPTION"
    HISTORICAL_INVALID_EVIDENCE = "HISTORICAL_INVALID_EVIDENCE"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EvidenceSource(FrozenModel):
    evidence_source_id: str
    evidence_type: str
    module: str
    artifact_type: str
    record_id: str
    artifact_relative_path: str
    source_fingerprint: str
    schema_version: int
    creation_sequence: int
    validation_status: str
    checksum_status: str
    limitations: tuple[str, ...] = ()
    display_label: str


class EvidenceValue(FrozenModel):
    value_id: str
    metric_name: str
    value: Any
    units: str
    source_ids: tuple[str, ...]
    calculation_method: str
    precision: int
    status: str
    limitations: tuple[str, ...]
    claim_classification: ClaimClassification

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fingerprint(self) -> str:
        return planning_fingerprint(self.model_dump(exclude={"fingerprint"}, mode="json"))


class EvidenceSnapshot(FrozenModel):
    schema_version: int
    status: str
    dashboard_schema_version: int
    database_schema_version: int
    mcp_catalogue_version: int
    mcp_tool_count: int
    sources: tuple[EvidenceSource, ...]
    values: tuple[EvidenceValue, ...]
    sections: dict[str, Any]
    source_checksums: dict[str, str]
    mandatory_source_count: int
    optional_source_count: int
    limitations: tuple[str, ...]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def snapshot_fingerprint(self) -> str:
        return planning_fingerprint(self.model_dump(exclude={"snapshot_fingerprint"}, mode="json"))
