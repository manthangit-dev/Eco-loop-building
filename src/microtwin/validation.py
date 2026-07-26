"""Fail-closed validation helpers for MicroTwin artifacts, features, rankings, and claims."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


class MicroTwinValidationError(ValueError):
    """A deterministic MicroTwin policy rejection with a stable reason code."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


REQUIRED_TELEMETRY_FIELDS = ("occupancy", "outdoor_temperature_c", "setpoint_c", "demand_w")


def validate_source_run(path: Path) -> None:
    """Reject a missing recorded run before dataset construction."""
    if not path.is_file():
        raise MicroTwinValidationError("missing_source_run")


def validate_aligned_telemetry(
    rows: Sequence[Mapping[str, Any]], *, expected_environment: str, target_zone: str
) -> tuple[Mapping[str, Any], ...]:
    """Validate causal telemetry and exclude explicitly non-usable callback rows."""
    accepted: list[Mapping[str, Any]] = []
    seen: set[tuple[object, object, object]] = set()
    previous_timestamp = ""
    for row in rows:
        if row.get("environment_id") != expected_environment:
            raise MicroTwinValidationError("wrong_environment")
        if row.get("zone") != target_zone:
            raise MicroTwinValidationError("missing_target_zone")
        if row.get("warmup") is True or row.get("api_ready") is False:
            continue
        for field in REQUIRED_TELEMETRY_FIELDS:
            if field not in row or row[field] is None:
                raise MicroTwinValidationError(f"missing_{field}")
            value = row[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise MicroTwinValidationError(
                    "invalid_units" if field != "occupancy" else "missing_occupancy"
                )
            if not math.isfinite(float(value)):
                raise MicroTwinValidationError(
                    "nan_rejected" if math.isnan(float(value)) else "infinity_rejected"
                )
        if row.get("temperature_units", "C") != "C" or row.get("demand_units", "W") != "W":
            raise MicroTwinValidationError("invalid_units")
        timestamp = str(row.get("timestamp", ""))
        if previous_timestamp and timestamp < previous_timestamp:
            raise MicroTwinValidationError("non_monotonic_timestamps")
        key = (row.get("environment_id"), row.get("zone"), timestamp)
        if key in seen:
            continue
        seen.add(key)
        previous_timestamp = timestamp
        accepted.append(row)
    return tuple(accepted)


def validate_transition_environments(environment_ids: Sequence[str]) -> None:
    if len(set(environment_ids)) != 1:
        raise MicroTwinValidationError("cross_environment_transition")


def validate_error_group(*, occupancy_values: Sequence[float], group: str) -> int:
    count = (
        sum(value > 0 for value in occupancy_values)
        if group == "occupied"
        else sum(value <= 0 for value in occupancy_values)
    )
    if count == 0:
        raise MicroTwinValidationError(f"missing_{group}_error_group")
    return count


def validate_rankings_agree(
    *, advisory_order: Sequence[str], microtwin_order: Sequence[str]
) -> None:
    if tuple(advisory_order) != tuple(microtwin_order):
        raise MicroTwinValidationError("rankings_disagree")


PROHIBITED_FEATURE_TOKENS = (
    "future_actual",
    "actual_future",
    "observed_future",
    "target_t_plus",
)


def validate_causal_features(feature_names: tuple[str, ...]) -> None:
    for name in feature_names:
        lowered = name.lower()
        if any(token in lowered for token in PROHIBITED_FEATURE_TOKENS):
            raise MicroTwinValidationError("prohibited_future_feature")


def load_validated_artifact(
    path: Path,
    *,
    expected_sha256: str,
    expected_feature_order: tuple[str, ...],
    expected_training_fingerprint: str,
) -> dict[str, Any]:
    if path.suffix.lower() != ".json":
        raise MicroTwinValidationError("unsafe_artifact_format")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise MicroTwinValidationError("artifact_checksum_mismatch")
    payload: Any = json.loads(content)
    if not isinstance(payload, dict):
        raise MicroTwinValidationError("unsafe_artifact_format")
    if tuple(payload.get("feature_names", ())) != expected_feature_order:
        raise MicroTwinValidationError("feature_schema_mismatch")
    if payload.get("training_fingerprint") != expected_training_fingerprint:
        raise MicroTwinValidationError("training_fingerprint_mismatch")
    return payload


def validate_ranking_inputs(
    *,
    thermal_qualified: bool,
    plan_ids: tuple[str, ...],
    context_ids: tuple[str, ...],
    model_ids: tuple[str, ...],
    caller_scores: dict[str, float] | None = None,
    authoritative_scores: dict[str, float] | None = None,
) -> None:
    if not thermal_qualified:
        raise MicroTwinValidationError("model_not_qualified")
    if len(set(context_ids)) != 1:
        raise MicroTwinValidationError("context_mismatch")
    if len(set(model_ids)) != 1:
        raise MicroTwinValidationError("model_context_mismatch")
    if not any(plan_id.startswith("710b98cc") for plan_id in plan_ids):
        raise MicroTwinValidationError("native_hold_reference_missing")
    if caller_scores is not None and authoritative_scores != caller_scores:
        raise MicroTwinValidationError("modified_score")


def validate_training_qualification(
    *, row_count: int, minimum_rows: int, improvement_fraction: float, minimum_improvement: float
) -> None:
    if row_count < minimum_rows:
        raise MicroTwinValidationError("insufficient_training_data")
    if improvement_fraction < minimum_improvement:
        raise MicroTwinValidationError("persistence_baseline_not_beaten")


def validate_candidate_fingerprint(*, supplied: str, calculated: str) -> None:
    if supplied != calculated:
        raise MicroTwinValidationError("candidate_fingerprint_mismatch")


def validate_caller_ranking(
    *, caller_order: tuple[str, ...], authoritative_order: tuple[str, ...]
) -> None:
    if caller_order != authoritative_order:
        raise MicroTwinValidationError("modified_ranking_order")


def validate_advisory_claim(text: str, evidence: dict[str, Any]) -> None:
    lowered = text.lower()
    rules = (
        ("actual energyplus result", "false_energyplus_result_claim"),
        ("energy saving", "unsupported_savings_claim"),
        ("% savings", "unsupported_savings_claim"),
        ("cost saving", "unsupported_cost_savings_claim"),
        ("$", "unsupported_cost_savings_claim"),
        ("carbon reduction", "unsupported_carbon_reduction_claim"),
        ("guaranteed comfort", "guaranteed_comfort_claim"),
        ("plan was executed", "false_physical_execution_claim"),
        ("physical action completed", "false_physical_execution_claim"),
    )
    for phrase, reason in rules:
        if phrase in lowered:
            raise MicroTwinValidationError(reason)
    evidence_ids = set(evidence.get("evidence_ids", ()))
    referenced = set(re.findall(r"tool_[a-zA-Z0-9_-]+", text))
    if not referenced <= evidence_ids:
        raise MicroTwinValidationError("invented_evidence_id")
    mae_match = re.search(r"thermal mae\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", lowered)
    if mae_match and abs(float(mae_match.group(1)) - float(evidence["thermal_mae"])) > 1e-6:
        raise MicroTwinValidationError("modified_metric_value")
    if evidence.get("require_uncertainty") and "12-step" not in lowered:
        raise MicroTwinValidationError("required_uncertainty_missing")
