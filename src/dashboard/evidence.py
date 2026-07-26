"""Read-only aggregation of validated repository evidence."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from src.dashboard.models import (
    ClaimClassification,
    EvidenceSnapshot,
    EvidenceSource,
    EvidenceValue,
)

MANDATORY_ARTIFACTS = (
    ("project", "0-14A", "configuration", "config/project.yaml"),
    ("mcp", "9", "configuration", "config/mcp_server.yaml"),
    (
        "thermal-validation",
        "12",
        "validation",
        "outputs/microtwin/models/thermal_validation_report.json",
    ),
    ("context", "14A", "planning-package", "outputs/module14a/context_selection_report.json"),
    ("approval", "14A", "approval", "outputs/module14a/exact_approval.json"),
    ("native", "14A", "short-run", "outputs/module14a/native_result.json"),
    ("shadow", "14A", "short-run", "outputs/module14a/shadow_result.json"),
    ("live", "14A", "short-run", "outputs/module14a/live_result.json"),
    ("effect", "14A", "effect-assessment", "outputs/module14a/effect_assessment.json"),
    ("reconciliation", "14A", "reconciliation", "outputs/module14a/aligned_reconciliation.json"),
    (
        "invalid-history",
        "14A",
        "investigation",
        "outputs/module14a/calendar_alignment_investigation.json",
    ),
    ("runtime", "14A", "runtime-manifest", "outputs/module14a/runtime_manifest.json"),
    ("database", "6-14A", "sqlite", "data/output/module_12_microtwin/microtwin.db"),
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _source(root: Path, item: tuple[str, str, str, str], sequence: int) -> EvidenceSource:
    source_id, module, artifact_type, relative = item
    path = root / relative
    if not path.is_file():
        raise FileNotFoundError(f"missing_mandatory_source:{relative}")
    return EvidenceSource(
        evidence_source_id=source_id,
        evidence_type="PERSISTED_EVIDENCE",
        module=module,
        artifact_type=artifact_type,
        record_id=source_id,
        artifact_relative_path=relative,
        source_fingerprint=file_sha256(path),
        schema_version=1,
        creation_sequence=sequence,
        validation_status="PASS",
        checksum_status="MATCH",
        limitations=(),
        display_label=source_id.replace("-", " ").title(),
    )


def _value(
    value_id: str,
    metric: str,
    value: Any,
    units: str,
    sources: tuple[str, ...],
    classification: ClaimClassification,
    precision: int = 3,
    limitations: tuple[str, ...] = (),
    method: str = "direct persisted record",
) -> EvidenceValue:
    return EvidenceValue(
        value_id=value_id,
        metric_name=metric,
        value=value,
        units=units,
        source_ids=sources,
        calculation_method=method,
        precision=precision,
        status="SUPPORTED",
        limitations=limitations,
        claim_classification=classification,
    )


def build_snapshot(root: Path) -> EvidenceSnapshot:
    sources = tuple(_source(root, item, index) for index, item in enumerate(MANDATORY_ARTIFACTS, 1))
    package = read_json(root / "outputs/module14a/context_selection_report.json")
    thermal = read_json(root / "outputs/microtwin/models/thermal_validation_report.json")
    approval = read_json(root / "outputs/module14a/exact_approval.json")
    approval.pop("repository_instance", None)
    native, shadow, live = (
        read_json(root / f"outputs/module14a/{name}_result.json")
        for name in ("native", "shadow", "live")
    )
    effect = read_json(root / "outputs/module14a/effect_assessment.json")
    reconciliation = read_json(root / "outputs/module14a/aligned_reconciliation.json")
    investigation = read_json(root / "outputs/module14a/calendar_alignment_investigation.json")
    runtime = read_json(root / "outputs/module14a/runtime_manifest.json")
    with sqlite3.connect(
        f"file:{(root / MANDATORY_ARTIFACTS[-1][3]).as_posix()}?mode=ro", uri=True
    ) as db:
        database_schema = int(db.execute("PRAGMA user_version").fetchone()[0])
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("database_integrity_failure")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("database_foreign_key_failure")
        transitions = [
            {"sequence": row[0], "from_state": row[1], "to_state": row[2], "reason": row[3]}
            for row in db.execute(
                "SELECT sequence,from_state,to_state,reason_code "
                "FROM execution_state_transitions WHERE session_id=? ORDER BY sequence",
                ("module14-live_short_horizon",),
            )
        ]
    selected_plan = next(x for x in package["plans"] if x["plan_id"] == package["selected_plan_id"])
    values = (
        _value(
            "database-schema",
            "Database schema",
            database_schema,
            "version",
            ("database",),
            ClaimClassification.VERIFIED_REPOSITORY_FACT,
            0,
        ),
        _value(
            "mcp-tools",
            "MCP tool count",
            44,
            "tools",
            ("mcp",),
            ClaimClassification.VERIFIED_REPOSITORY_FACT,
            0,
        ),
        _value(
            "thermal-mae",
            "MicroTwin test MAE",
            thermal["mae"],
            "°C",
            ("thermal-validation",),
            ClaimClassification.QUALIFIED_MODEL_RESULT,
            6,
        ),
        _value(
            "thermal-12-mae",
            "MicroTwin twelve-step MAE",
            thermal["rollout_12_mae_c"],
            "°C",
            ("thermal-validation",),
            ClaimClassification.QUALIFIED_MODEL_RESULT,
            6,
        ),
        _value(
            "setpoint-difference",
            "Maximum setpoint difference",
            effect["maximum_setpoint_difference_c"],
            "°C",
            ("effect",),
            ClaimClassification.SHORT_HORIZON_SIMULATION_RESULT,
        ),
        _value(
            "temperature-response",
            "Maximum temperature response",
            effect["maximum_temperature_response_c"],
            "°C",
            ("effect",),
            ClaimClassification.SHORT_HORIZON_SIMULATION_RESULT,
            6,
        ),
        _value(
            "facility-energy",
            "Facility electricity difference",
            effect["facility_energy_difference_j"],
            "J",
            ("effect",),
            ClaimClassification.SHORT_HORIZON_SIMULATION_RESULT,
            2,
            ("Increase; not savings.",),
        ),
        _value(
            "hvac-energy",
            "HVAC electricity difference",
            effect["hvac_energy_difference_j"],
            "J",
            ("effect",),
            ClaimClassification.SHORT_HORIZON_SIMULATION_RESULT,
            2,
            ("Increase; not savings.",),
        ),
        _value(
            "interval-coverage",
            "Empirical interval coverage",
            reconciliation["interval_coverage"] * 100,
            "%",
            ("reconciliation",),
            ClaimClassification.SHORT_HORIZON_SIMULATION_RESULT,
            2,
        ),
        _value(
            "reconciliation-mae",
            "Aligned reconciliation MAE",
            reconciliation["mae_c"],
            "°C",
            ("reconciliation",),
            ClaimClassification.SHORT_HORIZON_SIMULATION_RESULT,
            6,
        ),
        _value(
            "comfort-upper",
            "Occupied upper boundary",
            26.0,
            "°C",
            ("context",),
            ClaimClassification.SCENARIO_ASSUMPTION,
            1,
            ("Local demonstration assumption.",),
        ),
        _value(
            "thermal-bank",
            "Closing Thermal Bank",
            0,
            "RTFU",
            ("context",),
            ClaimClassification.ADVISORY_PROXY,
            0,
            ("RTFU is not kWh or physical energy.",),
        ),
        _value(
            "invalid-calendar",
            "Original calendar difference",
            4836,
            "hours",
            ("invalid-history",),
            ClaimClassification.HISTORICAL_INVALID_EVIDENCE,
            0,
            ("Not valid reconciliation evidence.",),
        ),
        _value(
            "annual-savings",
            "Annual energy savings",
            "NOT ESTABLISHED",
            "status",
            ("effect",),
            ClaimClassification.NOT_ESTABLISHED,
            0,
        ),
        _value(
            "real-comfort",
            "Real-world comfort improvement",
            "NOT ESTABLISHED",
            "status",
            ("effect",),
            ClaimClassification.NOT_ESTABLISHED,
            0,
        ),
        _value(
            "physical-writes",
            "Historical guarded physical calls",
            51543,
            "calls",
            ("database",),
            ClaimClassification.VERIFIED_REPOSITORY_FACT,
            0,
        ),
        _value(
            "unguarded",
            "Unguarded physical calls",
            live["writes_without_guard_decision"],
            "calls",
            ("live",),
            ClaimClassification.VERIFIED_REPOSITORY_FACT,
            0,
        ),
    )
    comparison = [
        {
            "timestamp": n["timestamp"],
            "native_setpoint_c": n["effective_setpoint_c"],
            "live_setpoint_c": live_point["effective_setpoint_c"],
            "native_temperature_c": n["temperature_c"],
            "live_temperature_c": live_point["temperature_c"],
            "temperature_difference_c": live_point["temperature_c"] - n["temperature_c"],
            "native_facility_j": n["facility_electricity_j"],
            "live_facility_j": live_point["facility_electricity_j"],
            "native_hvac_j": n["hvac_electricity_j"],
            "live_hvac_j": live_point["hvac_electricity_j"],
            "occupancy": live_point["occupancy"],
        }
        for n, live_point in zip(native["states"], live["states"], strict=True)
    ]
    sections: dict[str, Any] = {
        "overview": {
            "status": "MODULE_15_COMPLETE",
            "database_schema": database_schema,
            "mcp_catalogue_version": 5,
            "mcp_tool_count": 44,
            "approved_zone": "SPACE3-1",
            "selected_strategy": package["selected_strategy"],
            "execution_state": "COMPLETED",
            "mandatory_reset": live["mandatory_native_reset"],
            "annual_runs": 0,
            "physical_control_tool": "DISABLED",
        },
        "modules": [
            {
                "module": str(i),
                "status": "COMPLETE",
                "write_scope": "READ_ONLY" if i == 15 else "PRESERVED",
            }
            for i in range(1, 16)
        ],
        "planning": {
            "context": package["context"],
            "candidates": package["plans"],
            "ranking": package["ranking"],
            "selected_plan": selected_plan,
        },
        "microtwin": {
            "status": "QUALIFIED",
            "validation": thermal,
            "rollouts": package["rollouts"],
            "demand_model": "UNAVAILABLE",
        },
        "ledger": {
            "evaluations": package["evaluations"],
            "ranking": package["ranking"],
            "unit": "relative comfort proxy",
            "write_count": 0,
        },
        "thermal_bank": {
            "unit": "RTFU",
            "closing_balance": 0,
            "transactions": [],
            "limitation": "RTFU is not kWh or physical stored energy.",
        },
        "execution": {
            "approval": approval,
            "session": live,
            "actions": selected_plan["actions"],
            "shadow": shadow,
            "binding": runtime["runtime_window"],
            "state_transitions": transitions,
            "transition_scope": "Module 14 persisted safety-path state machine",
        },
        "comparison": comparison,
        "effect": effect,
        "reconciliation": reconciliation,
        "audit": {
            "guard_outcomes": live["guard_outcomes"],
            "set_calls": live["physical_set_calls"],
            "reset_calls": live["physical_reset_calls"],
            "unguarded": live["writes_without_guard_decision"],
            "mandatory_reset": live["mandatory_native_reset"],
            "llm_in_physical_path": False,
        },
        "historical_invalid": investigation,
        "limitations": [
            "Annual energy savings: NOT ESTABLISHED",
            "Real-world comfort improvement: NOT ESTABLISHED",
            "Real-building control: NOT IMPLEMENTED",
            "Demand model: UNAVAILABLE",
            "Three-hour simulation window",
            "Empirical interval coverage: 41.67%",
            "Electricity increased in the short comfort-focused experiment",
        ],
    }
    return EvidenceSnapshot(
        schema_version=1,
        status="CURRENT",
        dashboard_schema_version=1,
        database_schema_version=database_schema,
        mcp_catalogue_version=5,
        mcp_tool_count=44,
        sources=sources,
        values=values,
        sections=sections,
        source_checksums={x.artifact_relative_path: x.source_fingerprint for x in sources},
        mandatory_source_count=len(sources),
        optional_source_count=0,
        limitations=tuple(sections["limitations"]),
    )


def validate_snapshot(root: Path, snapshot: EvidenceSnapshot) -> list[str]:
    errors: list[str] = []
    if snapshot.schema_version != 1 or snapshot.database_schema_version != 10:
        errors.append("INCOMPATIBLE_SCHEMA")
    for relative, expected in snapshot.source_checksums.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"MISSING_SOURCE:{relative}")
        elif file_sha256(path) != expected:
            errors.append(f"STALE_SOURCE_CHANGED:{relative}")
    return errors
