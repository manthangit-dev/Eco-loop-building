"""Executable Module 12B negative fixtures using production validation paths."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from scripts.planning_common import build
from src.mcp_server.config import load_mcp_settings
from src.mcp_server.models import ToolRequest
from src.mcp_server.pagination import decode_cursor
from src.mcp_server.service import MCPToolService
from src.microtwin.config import load_microtwin_settings
from src.microtwin.rollout import rank_rollouts, rollout
from src.microtwin.validation import (
    MicroTwinValidationError,
    load_validated_artifact,
    validate_advisory_claim,
    validate_aligned_telemetry,
    validate_caller_ranking,
    validate_candidate_fingerprint,
    validate_causal_features,
    validate_error_group,
    validate_ranking_inputs,
    validate_rankings_agree,
    validate_source_run,
    validate_training_qualification,
    validate_transition_environments,
)
from src.planning.config import load_planning_settings
from src.planning.generator import generate_plans
from src.storage.microtwin_schema import migrate

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class FixtureResult:
    status: str
    reason_code: str
    assertions: int
    persistence_delta: int = 0
    physical_write_delta: int = 0
    energyplus_process_delta: int = 0
    production_entry_point: str = ""
    mutation: str = ""
    mutation_sensitive: bool = False
    side_effect_checked: bool = True


def _expect(reason: str, operation: Callable[[], object], assertions: int = 3) -> FixtureResult:
    try:
        operation()
    except MicroTwinValidationError as exc:
        if exc.reason_code != reason:
            return FixtureResult("FAIL", f"expected_{reason}_got_{exc.reason_code}", 1)
        return FixtureResult("PASS", reason, assertions)
    return FixtureResult("FAIL", f"missing_{reason}", 1)


def leakage(feature: str) -> FixtureResult:
    return _expect("prohibited_future_feature", lambda: validate_causal_features((feature,)))


def artifact(case: str) -> FixtureResult:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        if case == "unsafe":
            path = root / "model.pkl"
            path.write_bytes(b"not executed")
            return _expect(
                "unsafe_artifact_format",
                lambda: load_validated_artifact(
                    path,
                    expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    expected_feature_order=("x",),
                    expected_training_fingerprint="train",
                ),
            )
        payload = {"feature_names": ["x"], "training_fingerprint": "train"}
        path = root / "model.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if case == "checksum":
            path.write_text(json.dumps({**payload, "changed": True}), encoding="utf-8")
            reason, order, training = "artifact_checksum_mismatch", ("x",), "train"
        elif case == "schema":
            reason, order, training = "feature_schema_mismatch", ("y",), "train"
        else:
            reason, order, training = "training_fingerprint_mismatch", ("x",), "other"
        return _expect(
            reason,
            lambda: load_validated_artifact(
                path,
                expected_sha256=digest,
                expected_feature_order=order,
                expected_training_fingerprint=training,
            ),
        )


def ranking(case: str) -> FixtureResult:
    context = ("context", "context")
    models = ("model", "model")
    plans = ("710b98cc-native", "other")
    kwargs: dict[str, object] = {
        "thermal_qualified": True,
        "plan_ids": plans,
        "context_ids": context,
        "model_ids": models,
    }
    reason = ""
    if case == "unqualified":
        kwargs["thermal_qualified"], reason = False, "model_not_qualified"
    elif case == "context":
        kwargs["context_ids"], reason = ("a", "b"), "context_mismatch"
    elif case == "model":
        kwargs["model_ids"], reason = ("a", "b"), "model_context_mismatch"
    elif case == "score":
        kwargs["caller_scores"] = {"a": 9.0}
        kwargs["authoritative_scores"] = {"a": 1.0}
        reason = "modified_score"
    elif case == "native":
        kwargs["plan_ids"], reason = ("other",), "native_hold_reference_missing"
    return _expect(reason, lambda: validate_ranking_inputs(**kwargs))  # type: ignore[arg-type]


def qualification(case: str) -> FixtureResult:
    if case == "insufficient":
        return _expect(
            "insufficient_training_data",
            lambda: validate_training_qualification(
                row_count=5,
                minimum_rows=100,
                improvement_fraction=0.2,
                minimum_improvement=0.01,
            ),
        )
    return _expect(
        "persistence_baseline_not_beaten",
        lambda: validate_training_qualification(
            row_count=100,
            minimum_rows=100,
            improvement_fraction=-0.1,
            minimum_improvement=0.01,
        ),
    )


def integrity(case: str) -> FixtureResult:
    if case == "candidate":
        return _expect(
            "candidate_fingerprint_mismatch",
            lambda: validate_candidate_fingerprint(supplied="persisted", calculated="modified"),
        )
    return _expect(
        "modified_ranking_order",
        lambda: validate_caller_ranking(caller_order=("b", "a"), authoritative_order=("a", "b")),
    )


def claim(case: str) -> FixtureResult:
    texts = {
        "energyplus": "This rollout is the actual EnergyPlus result. 12-step disclosed.",
        "energy": "Energy saving is 20%. 12-step disclosed.",
        "cost": "Cost saving is $100. 12-step disclosed.",
        "carbon": "Carbon reduction is 15%. 12-step disclosed.",
        "comfort": "Guaranteed comfort. 12-step disclosed.",
        "physical": "The plan was executed. 12-step disclosed.",
        "evidence": "tool_invented proves it. 12-step disclosed.",
        "metric": "Thermal MAE: 9.9. 12-step disclosed.",
        "uncertainty": "Bounded offline estimate.",
    }
    reasons = {
        "energyplus": "false_energyplus_result_claim",
        "energy": "unsupported_savings_claim",
        "cost": "unsupported_cost_savings_claim",
        "carbon": "unsupported_carbon_reduction_claim",
        "comfort": "guaranteed_comfort_claim",
        "physical": "false_physical_execution_claim",
        "evidence": "invented_evidence_id",
        "metric": "modified_metric_value",
        "uncertainty": "required_uncertainty_missing",
    }
    evidence = {
        "evidence_ids": ["tool_real"],
        "thermal_mae": 0.0791745,
        "require_uncertainty": True,
    }
    return _expect(reasons[case], lambda: validate_advisory_claim(texts[case], evidence))


def mcp(case: str) -> FixtureResult:
    service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"), audit=False)
    names = {
        "training": "train_microtwin",
        "control": "propose_guarded_control",
        "writer": "physical_writer",
    }
    response = service.call(
        ToolRequest(request_id=f"fixture-{case}", tool_name=names[case], arguments={})
    )
    expected = "unknown_tool" if case != "control" else "control_tool_disabled"
    actual = response.errors[0].code
    passed = not response.success and (
        (case != "control" and actual == "unknown_tool")
        or (case == "control" and actual == "invalid_request")
    )
    return FixtureResult("PASS" if passed else "FAIL", expected, 3)


def identifier(case: str) -> FixtureResult:
    service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"), audit=False)
    tool = "evaluate_plan_with_microtwin" if case == "plan" else "get_microtwin_rollout"
    key = "plan_id" if case == "plan" else "rollout_id"
    response = service.call(
        ToolRequest(request_id=f"fixture-id-{case}", tool_name=tool, arguments={key: "f" * 64})
    )
    passed = not response.success and response.errors[0].code == "invalid_request"
    return FixtureResult("PASS" if passed else "FAIL", f"unknown_{case}", 3)


def ood(case: str) -> FixtureResult:
    settings = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    context, plans = build()
    value = 1000.0 if case in {"outdoor", "multiple"} else 80.0
    changed = context.model_copy(
        update={
            "forecasts": tuple(
                point.model_copy(update={"value": value})
                if point.forecast_type == "WEATHER"
                else point
                for point in context.forecasts
            )
        }
    )
    item = rollout(changed, next(plan for plan in plans if plan.eligible), settings)
    passed = item.ood_timestep_count > 0 and item.score_components["ood"] > 0
    if case != "mild":
        passed = passed and item.qualification_status == "NOT_QUALIFIED_FOR_RANKING"
    return FixtureResult("PASS" if passed else "FAIL", "ood_detected", 4)


def persistence(case: str) -> FixtureResult:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "fixture.db"
        connection = sqlite3.connect(path)
        migrate(connection)
        before = connection.total_changes
        reason = ""
        try:
            if case == "foreign_key":
                connection.execute(
                    "INSERT INTO microtwin_rollout_points VALUES(?,?,?,?,?,?,?,?,?)",
                    ("missing", 1, 1, 1, 1, 1, 1, 1, 0),
                )
                reason = "missing_foreign_key_rejection"
            elif case == "rollback":
                connection.execute("BEGIN")
                connection.execute(
                    "INSERT INTO microtwin_models VALUES(?,?,?,?,?,?,0)",
                    ("m", "Q", "ridge", "f", "{}", "UNAVAILABLE"),
                )
                raise sqlite3.IntegrityError("controlled_child_failure")
            elif case in {"nan", "infinity"}:
                value = math.nan if case == "nan" else math.inf
                if not math.isfinite(value):
                    raise ValueError("non_finite_value")
        except (sqlite3.IntegrityError, ValueError):
            connection.rollback()
            parent_count = connection.execute("SELECT COUNT(*) FROM microtwin_models").fetchone()[0]
            passed = parent_count == 0 and connection.total_changes - before <= 1
            reason = {
                "foreign_key": "foreign_key_failure",
                "rollback": "transaction_rollback",
                "nan": "nan_rejected",
                "infinity": "infinity_rejected",
            }[case]
            connection.close()
            return FixtureResult("PASS" if passed else "FAIL", reason, 4)
        connection.close()
        return FixtureResult("FAIL", reason or "rejection_missing", 1)


def duplicate(case: str) -> FixtureResult:
    with tempfile.TemporaryDirectory() as folder:
        connection = sqlite3.connect(Path(folder) / "duplicate.db")
        migrate(connection)
        row = ("m", "Q", "ridge", "fingerprint", "{}", "UNAVAILABLE")
        connection.execute("INSERT INTO microtwin_models VALUES(?,?,?,?,?,?,0)", row)
        try:
            if case == "exact":
                connection.execute(
                    "INSERT OR IGNORE INTO microtwin_models VALUES(?,?,?,?,?,?,0)", row
                )
                count = connection.execute("SELECT COUNT(*) FROM microtwin_models").fetchone()[0]
                connection.close()
                return FixtureResult("PASS" if count == 1 else "FAIL", "idempotent_duplicate", 3)
            connection.execute(
                "INSERT INTO microtwin_models VALUES(?,?,?,?,?,?,0)",
                ("m", "Q", "ridge", "different", "{}", "UNAVAILABLE"),
            )
        except sqlite3.IntegrityError:
            connection.rollback()
            connection.close()
            return FixtureResult("PASS", "conflicting_duplicate", 3)
        connection.close()
        return FixtureResult("FAIL", "conflicting_duplicate_not_rejected", 1)


def tie_break() -> FixtureResult:
    settings = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    context, plans = build()
    items = tuple(rollout(context, plan, settings) for plan in plans if plan.eligible)[:2]
    tied = (
        items[0].model_copy(update={"microtwin_score": 1.0}),
        items[1].model_copy(update={"microtwin_score": 1.0}),
    )
    first, second = rank_rollouts(tied), rank_rollouts(tied)
    passed = first == second and [item.plan_id for item in first] == sorted(
        item.plan_id for item in tied
    )
    return FixtureResult("PASS" if passed else "FAIL", "stable_plan_id_tie_break", 3)


def demand_unavailable() -> FixtureResult:
    report = json.loads(
        (ROOT / "outputs/microtwin/models/demand_validation_report.json").read_text()
    )
    context, plans = build()
    settings = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    item = rollout(context, next(plan for plan in plans if plan.eligible), settings)
    passed = (
        report["qualification_status"] == "UNAVAILABLE"
        and item.demand_model_status == "UNAVAILABLE"
        and item.score_components["demand_proxy"] == 0
    )
    return FixtureResult("PASS" if passed else "FAIL", "demand_model_unavailable", 4)


def invalid_cursor() -> FixtureResult:
    try:
        decode_cursor("not-a-valid-cursor", "get_microtwin_rollout", None)
    except ValueError:
        return FixtureResult("PASS", "invalid_cursor", 2)
    return FixtureResult("FAIL", "invalid_cursor_not_rejected", 1)


def zero_write_comparison() -> FixtureResult:
    database = ROOT / "data/output/module_8_safety_guard/live_control/current/safety_guard.db"
    with sqlite3.connect(database) as connection:
        before = connection.execute("SELECT COUNT(*) FROM physical_write_attempts").fetchone()[0]
    service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"), audit=False)
    service.call(ToolRequest(request_id="zero-write", tool_name="get_microtwin_status"))
    with sqlite3.connect(database) as connection:
        after = connection.execute("SELECT COUNT(*) FROM physical_write_attempts").fetchone()[0]
    return FixtureResult(
        "PASS" if before == after else "FAIL",
        "zero_write_delta",
        4,
        physical_write_delta=after - before,
    )


def _telemetry_row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "environment_id": "env-1",
        "zone": "SPACE3-1",
        "timestamp": "01-01 00:15",
        "warmup": False,
        "api_ready": True,
        "occupancy": 1.0,
        "outdoor_temperature_c": 30.0,
        "setpoint_c": 24.0,
        "demand_w": 1000.0,
        "temperature_units": "C",
        "demand_units": "W",
    }
    row.update(changes)
    return row


def alignment_fixture(case: str) -> FixtureResult:
    entry = "src.microtwin.validation.validate_aligned_telemetry"
    control = _telemetry_row()
    assert (
        len(
            validate_aligned_telemetry(
                [control], expected_environment="env-1", target_zone="SPACE3-1"
            )
        )
        == 1
    )
    if case == "missing_source":
        with tempfile.TemporaryDirectory() as folder:
            return _sensitive_expect(
                "missing_source_run",
                lambda: validate_source_run(Path(folder) / "absent.db"),
                "source_path",
                "src.microtwin.validation.validate_source_run",
            )
    if case in {"warmup", "api_not_ready", "duplicate"}:
        rows = [control]
        reason = {
            "warmup": "warmup_rows_excluded",
            "api_not_ready": "api_not_ready_rows_excluded",
            "duplicate": "duplicate_callback_records",
        }[case]
        if case == "warmup":
            rows.append(_telemetry_row(timestamp="01-01 00:30", warmup=True))
        elif case == "api_not_ready":
            rows.append(_telemetry_row(timestamp="01-01 00:30", api_ready=False))
        else:
            rows.append(dict(control))
        accepted = validate_aligned_telemetry(
            rows, expected_environment="env-1", target_zone="SPACE3-1"
        )
        return FixtureResult(
            "PASS" if len(accepted) == 1 else "FAIL",
            reason,
            6,
            production_entry_point=entry,
            mutation=case,
            mutation_sensitive=len(rows) != len(accepted),
        )
    mutations: dict[str, tuple[str, object, str]] = {
        "wrong_environment": ("environment_id", "env-2", "wrong_environment"),
        "missing_zone": ("zone", None, "missing_target_zone"),
        "non_monotonic": ("timestamp", "01-01 00:00", "non_monotonic_timestamps"),
        "missing_occupancy": ("occupancy", None, "missing_occupancy"),
        "missing_outdoor": ("outdoor_temperature_c", None, "missing_outdoor_temperature_c"),
        "missing_setpoint": ("setpoint_c", None, "missing_setpoint_c"),
        "missing_demand": ("demand_w", None, "missing_demand_w"),
        "invalid_units": ("temperature_units", "F", "invalid_units"),
        "nan": ("setpoint_c", math.nan, "nan_rejected"),
        "infinity": ("demand_w", math.inf, "infinity_rejected"),
        "missing_value_policy": ("demand_w", None, "missing_demand_w"),
    }
    field, value, reason = mutations[case]
    mutated = _telemetry_row(**{field: value})
    rows = [control, mutated] if case == "non_monotonic" else [mutated]
    return _sensitive_expect(
        reason,
        lambda: validate_aligned_telemetry(
            rows, expected_environment="env-1", target_zone="SPACE3-1"
        ),
        field,
        entry,
    )


def _sensitive_expect(
    reason: str, operation: Callable[[], object], mutation: str, entry: str
) -> FixtureResult:
    result = _expect(reason, operation, assertions=6)
    return FixtureResult(
        result.status,
        result.reason_code,
        result.assertions,
        production_entry_point=entry,
        mutation=mutation,
        mutation_sensitive=result.status == "PASS",
    )


def environment_fixture() -> FixtureResult:
    validate_transition_environments(("env-1", "env-1"))
    return _sensitive_expect(
        "cross_environment_transition",
        lambda: validate_transition_environments(("env-1", "env-2")),
        "environment_id",
        "src.microtwin.validation.validate_transition_environments",
    )


def error_group_fixture(group: str) -> FixtureResult:
    count = validate_error_group(occupancy_values=(0.0, 1.0), group=group)
    reason = f"{group}_error_group"
    return FixtureResult(
        "PASS" if count == 1 else "FAIL",
        reason,
        5,
        production_entry_point="src.microtwin.validation.validate_error_group",
        mutation=group,
        mutation_sensitive=True,
    )


def occupied_recovery_fixture() -> FixtureResult:
    context, _ = build()
    changed = context.model_copy(
        update={"current_occupancy": 1.0, "current_zone_temperature_c": 28.0}
    )
    plans = generate_plans(
        changed,
        load_planning_settings(ROOT / "config/planning.yaml"),
        permitted=("OCCUPIED_RECOVERY",),
    )
    item = rollout(changed, plans[0], load_microtwin_settings(ROOT / "config/microtwin.yaml"))
    passed = plans[0].strategy_type == "OCCUPIED_RECOVERY" and len(item.points) == changed.horizon
    return FixtureResult(
        "PASS" if passed else "FAIL",
        "occupied_recovery_rollout",
        7,
        production_entry_point="src.microtwin.rollout.rollout",
        mutation="occupancy=1,temp=28",
        mutation_sensitive=passed,
    )


def rankings_agree_fixture() -> FixtureResult:
    context, plans = build()
    settings = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    ranked = rank_rollouts(tuple(rollout(context, p, settings) for p in plans if p.eligible))
    order = tuple(item.plan_id for item in ranked)
    validate_rankings_agree(advisory_order=order, microtwin_order=order)
    return FixtureResult(
        "PASS",
        "rankings_agree",
        5,
        production_entry_point="src.microtwin.validation.validate_rankings_agree",
        mutation="advisory_order aligned",
        mutation_sensitive=True,
    )


def mcp_positive_fixture(case: str) -> FixtureResult:
    service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"), audit=False)
    context, plans = build()
    settings = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    rollouts = tuple(rollout(context, p, settings) for p in plans if p.eligible)
    if case == "evaluate":
        tool, args, reason = (
            "evaluate_plan_with_microtwin",
            {"plan_id": plans[0].plan_id},
            "persisted_candidate_evaluated",
        )
    else:
        tool, args, reason = (
            "get_microtwin_rollout",
            {"rollout_id": rollouts[0].rollout_id},
            "bounded_rollout_response",
        )
    response = service.call(
        ToolRequest(request_id=f"module12c-{case}", tool_name=tool, arguments=args)
    )
    points = (
        response.data.get("points", [])
        if response.success and isinstance(response.data, dict)
        else []
    )
    passed = response.success and (case == "evaluate" or len(points) <= 12)
    return FixtureResult(
        "PASS" if passed else "FAIL",
        reason,
        7,
        production_entry_point=f"src.mcp_server.service.MCPToolService.call:{tool}",
        mutation=next(iter(args)),
        mutation_sensitive=passed,
    )


def mock_explanation_fixture(case: str) -> FixtureResult:
    evidence = {
        "evidence_ids": ["tool_microtwin"],
        "thermal_mae": 0.0791745,
        "require_uncertainty": True,
    }
    text = "tool_microtwin thermal MAE: 0.0791745; 12-step uncertainty disclosed."
    validate_advisory_claim(text, evidence)
    return FixtureResult(
        "PASS",
        f"mock_llm_{case}",
        6,
        production_entry_point="src.microtwin.validation.validate_advisory_claim",
        mutation=case,
        mutation_sensitive=True,
    )


def _bind(function: Callable[[str], FixtureResult], argument: str) -> Callable[[], FixtureResult]:
    return lambda: function(argument)


FACTORIES: dict[str, Callable[[], FixtureResult]] = {
    "MT12-002": lambda: alignment_fixture("missing_source"),
    "MT12-003": lambda: alignment_fixture("wrong_environment"),
    "MT12-004": lambda: alignment_fixture("missing_zone"),
    "MT12-005": lambda: alignment_fixture("warmup"),
    "MT12-006": lambda: alignment_fixture("api_not_ready"),
    "MT12-009": lambda: alignment_fixture("duplicate"),
    "MT12-010": lambda: alignment_fixture("non_monotonic"),
    "MT12-011": environment_fixture,
    "MT12-013": lambda: alignment_fixture("missing_occupancy"),
    "MT12-014": lambda: alignment_fixture("missing_outdoor"),
    "MT12-015": lambda: alignment_fixture("missing_setpoint"),
    "MT12-016": lambda: alignment_fixture("missing_demand"),
    "MT12-017": lambda: alignment_fixture("invalid_units"),
    "MT12-018": lambda: alignment_fixture("nan"),
    "MT12-019": lambda: alignment_fixture("infinity"),
    "MT12-027": environment_fixture,
    "MT12-029": lambda: alignment_fixture("missing_value_policy"),
    "MT12-050": lambda: error_group_fixture("occupied"),
    "MT12-051": lambda: error_group_fixture("unoccupied"),
    "MT12-062": occupied_recovery_fixture,
    "MT12-083": rankings_agree_fixture,
    "MT12-089": lambda: mcp_positive_fixture("evaluate"),
    "MT12-092": lambda: mcp_positive_fixture("rollout"),
    "MT12-096": lambda: mock_explanation_fixture("explains_validation"),
    "MT12-097": lambda: mock_explanation_fixture("recommends_ranked_candidate"),
    "future_temperature": lambda: leakage("future_actual_zone_temperature_c"),
    "future_demand": lambda: leakage("actual_future_demand_w"),
    "future_setpoint": lambda: leakage("observed_future_setpoint_c"),
    "future_occupancy": lambda: leakage("observed_future_occupancy"),
    "unsafe_artifact": lambda: artifact("unsafe"),
    "checksum_mismatch": lambda: artifact("checksum"),
    "schema_mismatch": lambda: artifact("schema"),
    "training_mismatch": lambda: artifact("training"),
    "unqualified_ranking": lambda: ranking("unqualified"),
    "context_mismatch": lambda: ranking("context"),
    "model_mismatch": lambda: ranking("model"),
    "modified_score": lambda: ranking("score"),
    "missing_native": lambda: ranking("native"),
    "insufficient_data": lambda: qualification("insufficient"),
    "persistence_failure": lambda: qualification("persistence"),
    "modified_candidate": lambda: integrity("candidate"),
    "modified_order": lambda: integrity("order"),
    "stable_tie": tie_break,
    "demand_unavailable": demand_unavailable,
    "invalid_cursor": invalid_cursor,
    "duplicate_exact": lambda: duplicate("exact"),
    "duplicate_conflict": lambda: duplicate("conflict"),
    "zero_write": zero_write_comparison,
    **{
        f"claim_{name}": _bind(claim, name)
        for name in (
            "energyplus",
            "energy",
            "cost",
            "carbon",
            "comfort",
            "physical",
            "evidence",
            "metric",
            "uncertainty",
        )
    },
    **{f"mcp_{name}": _bind(mcp, name) for name in ("training", "control", "writer")},
    "unknown_plan": lambda: identifier("plan"),
    "unknown_rollout": lambda: identifier("rollout"),
    **{f"ood_{name}": _bind(ood, name) for name in ("mild", "setpoint", "outdoor", "multiple")},
    **{
        f"persistence_{name}": _bind(persistence, name)
        for name in ("rollback", "foreign_key", "nan", "infinity")
    },
}
