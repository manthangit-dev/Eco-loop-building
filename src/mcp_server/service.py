"""Deterministic handlers backed by persisted Modules 6–8 evidence."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from src.control.models import ActuatorIdentity
from src.ledger.config import load_comfort_ledger_settings
from src.ledger.evaluation import evaluate_candidates, rank_evaluations
from src.mcp_server.config import MCPSettings
from src.mcp_server.models import (
    ControlProposalInput,
    ToolClassification,
    ToolDefinition,
    ToolEnvelope,
    ToolError,
    ToolRequest,
    fingerprint,
)
from src.mcp_server.pagination import decode_cursor, encode_cursor
from src.mcp_server.registry import build_registry, catalogue_fingerprint
from src.microtwin.config import load_microtwin_settings
from src.microtwin.rollout import rank_rollouts, rollout
from src.planning.config import load_planning_settings
from src.planning.context import build_context
from src.planning.generator import generate_plans, select_deterministic
from src.safety.config import load_safety_settings
from src.safety.guard import SafetyGuard
from src.safety.memory import SafetyMemory
from src.safety.models import ProposedCommand
from src.storage.mcp_store import MCPAuditStore
from src.storage.planning_store import PlanningStore
from src.thermal_bank.config import load_thermal_bank_settings

Handler = Callable[[dict[str, Any]], tuple[Any, dict[str, Any]]]


class MCPToolService:
    def __init__(self, settings: MCPSettings, *, audit: bool = True) -> None:
        self.settings = settings
        self.registry = build_registry(settings.control_tools_enabled)
        self.definitions = {item.name: item for item in self.registry}
        self.catalogue_fingerprint = catalogue_fingerprint(self.registry)
        self.audit = audit
        self.handlers: dict[str, Handler] = {
            name: getattr(self, f"_tool_{name}") for name in self.definitions
        }

    def call(self, request: ToolRequest) -> ToolEnvelope:
        definition = self.definitions.get(request.tool_name)
        if definition is None:
            definition = ToolDefinition(
                name=request.tool_name,
                purpose="Unregistered tool",
                classification=ToolClassification.READ_ONLY,
                enabled=False,
            )
            response = self._error(request, "unknown_tool", "Tool is not registered.")
            if self.audit:
                with MCPAuditStore(
                    self.settings.audit_database, self.settings.output_root
                ) as store:
                    existing = store.existing(request)
                    if existing is not None:
                        return existing
                    store.append(request, definition, response)
            return response
        if request.schema_version != 1:
            return self._error(request, "schema_version_mismatch", "Tool schema version must be 1.")
        if self.audit:
            with MCPAuditStore(self.settings.audit_database, self.settings.output_root) as store:
                try:
                    existing = store.existing(request)
                except ValueError:
                    return self._error(
                        request, "conflicting_duplicate", "Request ID payload differs."
                    )
                if existing is not None:
                    return existing
        try:
            data, provenance = self.handlers[request.tool_name](request.arguments)
            response = self._success(request, data, provenance)
        except (KeyError, ValueError, ValidationError, sqlite3.Error) as exc:
            response = self._error(request, "invalid_request", str(exc))
        except Exception as exc:
            response = self._error(request, "handler_error", f"{type(exc).__name__}: {exc}")
        if self.audit:
            with MCPAuditStore(self.settings.audit_database, self.settings.output_root) as store:
                store.append(request, definition, response)
        return response

    def _success(self, request: ToolRequest, data: Any, provenance: dict[str, Any]) -> ToolEnvelope:
        call_id = fingerprint(request.model_dump(mode="json"))
        payload: dict[str, Any] = {
            "request_id": request.request_id,
            "tool_call_id": call_id,
            "tool_name": request.tool_name,
            "tool_schema_version": 1,
            "success": True,
            "data": data,
            "errors": [],
            "warnings": [],
            "run_id": request.arguments.get("run_id"),
            "environment_id": None,
            "source_timestamp": None,
            "processing_metadata": "deterministic_recorded_artifact",
            "truncated": False,
            "next_cursor": None,
            "provenance": provenance,
        }
        return ToolEnvelope(
            request_id=request.request_id,
            tool_call_id=call_id,
            tool_name=request.tool_name,
            tool_schema_version=1,
            success=True,
            data=data,
            run_id=request.arguments.get("run_id"),
            processing_metadata="deterministic_recorded_artifact",
            provenance=provenance,
            fingerprint=fingerprint(payload),
        )

    def _error(self, request: ToolRequest, code: str, message: str) -> ToolEnvelope:
        call_id = fingerprint(request.model_dump(mode="json"))
        error = ToolError(code=code, message=message)
        payload: dict[str, Any] = {
            "request_id": request.request_id,
            "tool_call_id": call_id,
            "tool_name": request.tool_name,
            "tool_schema_version": 1,
            "success": False,
            "data": None,
            "errors": [error.model_dump(mode="json")],
            "warnings": [],
            "run_id": request.arguments.get("run_id"),
            "environment_id": None,
            "source_timestamp": None,
            "processing_metadata": "deterministic_recorded_artifact",
            "truncated": False,
            "next_cursor": None,
            "provenance": {},
        }
        return ToolEnvelope(
            request_id=request.request_id,
            tool_call_id=call_id,
            tool_name=request.tool_name,
            tool_schema_version=1,
            success=False,
            errors=(error,),
            run_id=request.arguments.get("run_id"),
            processing_metadata="deterministic_recorded_artifact",
            fingerprint=fingerprint(payload),
        )

    def _run(self, arguments: dict[str, Any]) -> tuple[str, Path]:
        run_id = str(arguments["run_id"])
        return run_id, self.settings.run_path(run_id)

    def _limit(self, arguments: dict[str, Any]) -> int:
        value = int(arguments.get("limit", self.settings.default_rows))
        if not 0 < value <= self.settings.maximum_rows:
            raise ValueError("limit outside configured bounds")
        return value

    def _state_database(self, path: Path) -> Path:
        database = path / "thermoledger_state.db"
        if not database.exists():
            raise ValueError("state database unavailable")
        return database

    def _safety_database(self, path: Path) -> Path:
        database = path / "safety_guard.db"
        if not database.exists():
            raise ValueError("safety database unavailable")
        return database

    def _read(
        self, database: Path, sql: str, params: tuple[object, ...] = ()
    ) -> list[dict[str, Any]]:
        connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        rows = [dict(row) for row in connection.execute(sql, params).fetchall()]
        connection.close()
        return rows

    def _tool_list_available_runs(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        limit = self._limit(arguments)
        offset = (
            decode_cursor(str(arguments["cursor"]), "list_available_runs", None)
            if "cursor" in arguments
            else 0
        )
        items = []
        for run_id, path in self.settings.runs:
            summary_path = path / "fallback_controller_summary.json"
            summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
            items.append(
                {
                    "run_id": run_id,
                    "run_type": run_id.split("-", 1)[1],
                    "status": "COMPLETED",
                    "state_count": summary.get("state_count", 35040),
                    "controller_decision_count": summary.get("decision_count", 0),
                    "safety_decision_count": summary.get("guard_decision_count", 0),
                    "physical_write_count": summary.get("set_call_count", 0)
                    + summary.get("reset_count", 0),
                    "energyplus_exit_code": summary.get("energyplus_exit_code", 0),
                }
            )
        page = items[offset : offset + limit]
        next_cursor = (
            encode_cursor("list_available_runs", None, offset + limit)
            if offset + limit < len(items)
            else None
        )
        return {"items": page, "next_cursor": next_cursor}, {
            "source": "configured_recorded_runs",
            "ordering": "configuration_order",
        }

    def _tool_get_run_metadata(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        run_id, path = self._run(arguments)
        summary_path = path / "fallback_controller_summary.json"
        summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
        return (
            {
                "run_id": run_id,
                "status": "COMPLETED",
                "path": str(path.relative_to(self.settings.root)),
                "model_checksum": summary.get("model_checksum"),
                "weather_checksum": summary.get("weather_checksum"),
                "controller_mode": summary.get("mode"),
                "safety_guard_status": summary.get("safety_guard_status"),
                "limitations": ["recorded artifact", "final annual command may be right-censored"],
            },
            {"source": "run summary", "schema_version": 4},
        )

    def _tool_get_building_state(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        run_id, path = self._run(arguments)
        database = self._state_database(path)
        sequence = arguments.get("state_id")
        where, params = ("sequence=?", (int(sequence),)) if sequence is not None else ("1=1", ())
        states = self._read(
            database,
            f"SELECT * FROM building_states WHERE {where} ORDER BY sequence DESC LIMIT 1",
            params,
        )
        if not states:
            raise ValueError("state not found")
        state = states[0]
        zones = self._read(
            database,
            """SELECT zone_id,exact_name,classification,is_plenum,occupant_count,
            mean_air_temperature_c,effective_cooling_setpoint_c,
            relative_humidity_percent,pmv,co2_ppm FROM zone_states
            WHERE building_state_id=? ORDER BY zone_id""",
            (state["id"],),
        )
        zone_filter = arguments.get("zone")
        if zone_filter is not None:
            zones = [zone for zone in zones if zone["exact_name"] == zone_filter]
        timestamp = (
            f"{int(state['month']):02}-{int(state['day']):02} "
            f"{int(state['hour']):02}:{int(state['minute']):02}"
        )
        return {
            "run_id": run_id,
            "state_id": state["sequence"],
            "simulation_timestamp": timestamp,
            "environment_id": state["environment_number"],
            "warmup": bool(state["warmup"]),
            "outdoor_dry_bulb_c": state["outdoor_dry_bulb_c"],
            "zones": zones,
            "schema_version": state["schema_version"],
        }, {
            "database": str(database.relative_to(self.settings.root)),
            "table": "building_states,zone_states",
        }

    def _tool_get_zone_state(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        copied = dict(arguments)
        copied["zone"] = str(arguments["zone"])
        data, provenance = self._tool_get_building_state(copied)
        zones = data["zones"]
        if len(zones) != 1:
            raise ValueError("exact zone not found")
        zone = zones[0]
        zone["observable"] = True
        zone["conditioned"] = zone["classification"] == "OCCUPIED_CONDITIONED"
        zone["occupied"] = float(zone["occupant_count"]) > 0
        zone["approved_for_control"] = zone["exact_name"] == "SPACE3-1"
        return zone, provenance

    def _tool_get_recent_state_history(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, path = self._run(arguments)
        limit = min(self._limit(arguments), self.settings.maximum_history_points)
        zone = str(arguments.get("zone", "SPACE3-1"))
        rows = self._read(
            self._state_database(path),
            """SELECT b.sequence,z.mean_air_temperature_c,z.occupant_count,
            z.effective_cooling_setpoint_c FROM building_states b JOIN zone_states z
            ON z.building_state_id=b.id WHERE z.exact_name=? ORDER BY b.sequence DESC LIMIT ?""",
            (zone, limit),
        )
        rows.reverse()
        return {
            "original_point_count": len(rows),
            "returned_point_count": len(rows),
            "downsampled": False,
            "points": rows,
        }, {"ordering": "ascending_sequence"}

    def _tool_get_controller_status(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        raw = yaml.safe_load((self.settings.root / "config/fallback_controller.yaml").read_text())
        return {
            "enabled": raw["controller"]["enabled"],
            "schema_version": raw["controller"]["schema_version"],
            "decision_interval": raw["controller"]["decision_interval_zone_timesteps"],
            "hysteresis_celsius": raw["occupied_policy"]["hysteresis_celsius"],
            "minimum_hold": raw["occupied_policy"]["minimum_hold_zone_timesteps"],
            "occupancy_grace": raw["occupied_policy"]["occupancy_grace_zone_timesteps"],
            "command_ttl": raw["staleness"]["command_ttl_zone_timesteps"],
            "approved_target": raw["targets"]["real_actuation_zone"],
        }, {"source": "config/fallback_controller.yaml"}

    def _tool_get_controller_decisions(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, path = self._run(arguments)
        rows = self._read(
            self._state_database(path),
            """SELECT d.decision_id,d.based_on_state_sequence,
            d.mode_after,d.reason_code,d.requested_setpoint_celsius,c.command_id
            FROM control_decisions d LEFT JOIN control_commands c ON c.decision_id=d.decision_id
            ORDER BY d.decision_sequence DESC LIMIT ?""",
            (self._limit(arguments),),
        )
        return rows, {"ordering": "newest_first", "table": "control_decisions"}

    def _tool_get_safety_guard_status(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        raw = yaml.safe_load((self.settings.root / "config/safety_guard.yaml").read_text())
        return {
            "enabled": raw["safety"]["enabled"],
            "schema_version": raw["safety"]["schema_version"],
            "fail_closed": raw["safety"]["fail_closed"],
            "approved_actuator": raw["approved_actuator"],
            "approved_zones": raw["approved_zones"],
            "limits": raw["limits"],
            "runtime": raw["runtime"],
        }, {"source": "config/safety_guard.yaml"}

    def _tool_get_safety_decisions(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        _, path = self._run(arguments)
        rows = self._read(
            self._safety_database(path),
            """SELECT d.guard_decision_id,d.command_id,
            d.outcome,d.reason_code,d.actuator_identity,d.requested_value,d.applied_value,
            g.physical_submission_status FROM safety_guard_decisions d LEFT JOIN guarded_commands g
            ON g.guard_decision_id=d.guard_decision_id ORDER BY d.persisted_order DESC LIMIT ?""",
            (self._limit(arguments),),
        )
        return rows, {"ordering": "newest_first", "schema_version": 3}

    def _tool_get_physical_write_audit(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, path = self._run(arguments)
        rows = self._read(
            self._safety_database(path),
            """SELECT attempt_id,guarded_command_id,
            guard_decision_id,operation,permitted,applied_value,callback_context_json,reason_code
            FROM physical_write_attempts ORDER BY attempt_id DESC LIMIT ?""",
            (self._limit(arguments),),
        )
        return rows, {"ordering": "newest_first", "table": "physical_write_attempts"}

    def _tool_inspect_energyplus_errors(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, path = self._run(arguments)
        summary_path = path / "fallback_controller_summary.json"
        summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
        return (
            {
                "warning_count": summary.get("warning_count", 0),
                "severe_count": summary.get("severe_count", 0),
                "fatal_count": summary.get("fatal_count", 0),
                "entries": [],
                "truncated": False,
            },
            {"source": "recorded EnergyPlus summary"},
        )

    def _tool_get_energyplus_execution_status(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, path = self._run(arguments)
        summary = json.loads((path / "fallback_controller_summary.json").read_text())
        keys = (
            "energyplus_exit_code",
            "callback_error_count",
            "api_error_count",
            "subscriber_error_count",
            "persistence_error_count",
            "warning_count",
            "severe_count",
            "fatal_count",
        )
        return {key: summary.get(key, 0) for key in keys}, {
            "source": "fallback_controller_summary.json"
        }

    def _tool_list_available_actuators(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        zones = ("SPACE1-1", "SPACE2-1", "SPACE3-1", "SPACE4-1", "SPACE5-1")
        items = [
            {
                "component_type": "Zone Temperature Control",
                "control_type": "Cooling Setpoint",
                "actuator_key": zone,
                "units": "C",
                "zone": zone,
                "approved": zone == "SPACE3-1",
                "rejection_reason": None if zone == "SPACE3-1" else "not in Module 8 allowlist",
            }
            for zone in zones
        ]
        if arguments.get("approved_only"):
            items = [item for item in items if item["approved"]]
        return items[: self._limit(arguments)], {"source": "Module 5 verified discovery evidence"}

    def _energy_values(self, path: Path) -> tuple[float, float, int]:
        rows = self._read(
            self._state_database(path),
            """SELECT AVG(facility_purchased_electricity_raw_j) facility,
            AVG(hvac_electricity_raw_j) hvac,COUNT(*) count FROM building_states""",
        )
        return float(rows[0]["facility"]), float(rows[0]["hvac"]), int(rows[0]["count"])

    def _tool_get_run_energy_summary(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        _, path = self._run(arguments)
        facility, hvac, count = self._energy_values(path)
        return (
            {
                "state_count": count,
                "mean_facility_electricity_raw_j": facility,
                "mean_hvac_electricity_raw_j": hvac,
                "claim": "diagnostic recorded values; not savings",
            },
            {"table": "building_states"},
        )

    def _tool_compare_runs(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        first = self.settings.run_path(str(arguments["reference_run_id"]))
        second = self.settings.run_path(str(arguments["experimental_run_id"]))
        a, b = self._energy_values(first), self._energy_values(second)
        if a[2] != b[2]:
            raise ValueError("incompatible state counts")
        return (
            {
                "state_count": a[2],
                "facility_diagnostic_difference_j": b[0] - a[0],
                "hvac_diagnostic_difference_j": b[1] - a[1],
                "savings_claim": False,
            },
            {"alignment": "equal annual state count"},
        )

    def _tool_get_comfort_evidence(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        _, path = self._run(arguments)
        row = self._read(
            self._state_database(path),
            """SELECT COUNT(*) total,
            SUM(CASE WHEN occupant_count>0 THEN 1 ELSE 0 END) occupied,
            SUM(CASE WHEN pmv IS NOT NULL THEN 1 ELSE 0 END) pmv_available,
            SUM(CASE WHEN co2_ppm IS NOT NULL THEN 1 ELSE 0 END) co2_available FROM zone_states""",
        )[0]
        return (
            {
                **row,
                "comfort_equity_score": None,
                "claim": "coverage evidence only; no comfort-improvement claim",
            },
            {"table": "zone_states"},
        )

    def _tool_validate_control_proposal(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        item = ControlProposalInput.model_validate(arguments)
        settings = load_safety_settings(self.settings.root / "config/safety_guard.yaml")
        identity = ActuatorIdentity(
            item.component_type, item.control_type, item.actuator_key, item.units
        )
        proposal = ProposedCommand(
            item.client_request_id,
            "mcp-dry-run",
            item.run_id,
            item.environment_id,
            item.zone,
            identity,
            item.requested_value,
            item.source_state_sequence,
            item.decision_sequence or item.source_state_sequence,
            item.valid_from_sequence or item.source_state_sequence + 1,
            item.expires_after_sequence or item.source_state_sequence + 2,
            item.current_sequence,
            item.source_state_sequence / 4,
            item.source_state_sequence / 4,
            item.current_sequence / 4,
        )
        decision, guarded = SafetyGuard(
            settings, SafetyMemory(item.run_id, item.environment_id)
        ).evaluate(proposal)
        return {
            "accepted_for_potential_execution": guarded is not None
            and decision.applied_value is not None,
            "guard_outcome": decision.outcome.value,
            "reason_code": decision.reason.value,
            "requested_value": item.requested_value,
            "safe_applied_value": decision.applied_value,
            "canonical_actuator_identity": identity.key,
            "physical_write_count": 0,
            "no_write_confirmation": True,
        }, {"boundary": "Module 8 dry-run; no writer"}

    def _tool_propose_guarded_control(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        if not self.settings.control_tools_enabled:
            raise ValueError("control-capable MCP tool is disabled by configuration")
        if arguments.get("runtime_mode") != self.settings.control_runtime_mode:
            raise ValueError("guarded_control runtime mode required")
        raise ValueError("no active live EnergyPlus run is registered")

    def _planning(self, arguments: dict[str, Any]) -> tuple[Any, tuple[Any, ...], Any]:
        settings = load_planning_settings(self.settings.root / "config/planning.yaml")
        run_id = str(arguments.get("run_id", "module8-live-control"))
        path = self.settings.run_path(run_id)
        context = build_context(
            settings,
            run_id,
            self._state_database(path),
            int(arguments.get("source_state_id", 19345)),
            str(arguments.get("environment_id", "weather-3")),
            str(arguments.get("zone", "SPACE3-1")),
            int(arguments.get("horizon", settings.default_horizon)),
        )
        plans = generate_plans(context, settings)
        with PlanningStore(settings.database, settings.output_root) as store:
            store.persist(context, plans)
        return context, plans, settings

    def _tool_get_forecast_context(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        context, _, _ = self._planning(arguments)
        return context.model_dump(mode="json"), {
            "source": "local versioned scenarios",
            "advisory_only": True,
        }

    def _tool_generate_candidate_plans(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        context, plans, _ = self._planning(arguments)
        return {
            "context_id": context.context_id,
            "candidates": [plan.model_dump(mode="json") for plan in plans],
            "physical_write_count": 0,
            "no_write_confirmation": True,
        }, {"generator": "deterministic_module_11"}

    def _tool_evaluate_candidate_plan(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, plans, _ = self._planning(arguments)
        plan_id = str(arguments["plan_id"])
        plan = next((item for item in plans if item.plan_id == plan_id), None)
        if plan is None:
            raise ValueError("candidate_not_found")
        return plan.model_dump(mode="json"), {"source": "persisted deterministic candidate"}

    def _tool_compare_candidate_plans(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, plans, _ = self._planning(arguments)
        return {
            "ranking": [
                {
                    "plan_id": p.plan_id,
                    "strategy": p.strategy_type,
                    "eligible": p.eligible,
                    "advisory_score": p.advisory_score,
                }
                for p in plans
            ],
            "deterministic_selected_plan": select_deterministic(plans).plan_id,
        }, {"tie_break": "score,strategy,plan_id"}

    def _tool_get_planning_session(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        _, _, settings = self._planning(arguments)
        connection = sqlite3.connect(f"file:{settings.database.resolve()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM planning_sessions WHERE session_id=?", (str(arguments["session_id"]),)
        ).fetchone()
        connection.close()
        if row is None:
            raise ValueError("planning_session_not_found")
        return dict(row), {"source": "planning_sessions"}

    def _tool_select_advisory_plan(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        context, plans, settings = self._planning(arguments)
        plan_id = str(arguments["plan_id"])
        plan = next((item for item in plans if item.plan_id == plan_id and item.eligible), None)
        if plan is None:
            raise ValueError("ineligible_or_invented_candidate")
        deterministic = select_deterministic(plans)
        session_id = fingerprint({"context": context.context_id, "selected": plan_id})
        with sqlite3.connect(settings.database) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(
                "INSERT OR IGNORE INTO planning_sessions VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    session_id,
                    context.context_id,
                    deterministic.plan_id,
                    plan_id,
                    "MATCH" if deterministic.plan_id == plan_id else "DISAGREE",
                    "COMPLETED",
                    0,
                    "mcp_advisory",
                    "deterministic",
                    fingerprint({"session": session_id}),
                ),
            )
            connection.execute(
                "INSERT OR IGNORE INTO plan_selections VALUES(?,?,?,?,?,1)",
                (
                    fingerprint({"selection": session_id}),
                    session_id,
                    plan_id,
                    "LLM_ADVISORY_SELECTION",
                    "PASS",
                ),
            )
        return {
            "session_id": session_id,
            "selected_plan_id": plan_id,
            "deterministic_plan_id": deterministic.plan_id,
            "agreement": plan_id == deterministic.plan_id,
            "advisory_only": True,
            "physical_write_performed": False,
        }, {"policy": "existing_eligible_candidates_only"}

    def _microtwin(self) -> tuple[Any, tuple[Any, ...], Any, tuple[Any, ...]]:
        context, plans, _ = self._planning({})
        settings = load_microtwin_settings(self.settings.root / "config/microtwin.yaml")
        rollouts = tuple(rollout(context, plan, settings) for plan in plans if plan.eligible)
        return context, plans, settings, rollouts

    def _tool_get_microtwin_status(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        _, _, settings, _ = self._microtwin()
        manifest = json.loads((settings.model_directory / "model_manifest.json").read_text())
        return manifest, {"source": "safe JSON model artifact"}

    def _tool_get_microtwin_validation(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, _, settings, _ = self._microtwin()
        report = json.loads(
            (settings.model_directory / "thermal_validation_report.json").read_text()
        )
        return report, {"source": "chronological held-out test"}

    def _tool_evaluate_plan_with_microtwin(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, plans, _, rollouts = self._microtwin()
        plan_id = str(arguments["plan_id"])
        if not any(plan.plan_id == plan_id and plan.eligible for plan in plans):
            raise ValueError("unknown_or_ineligible_plan")
        item = next(value for value in rollouts if value.plan_id == plan_id)
        return item.model_dump(mode="json"), {"boundary": "offline counterfactual; zero writes"}

    def _tool_compare_microtwin_rollouts(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, _, _, rollouts = self._microtwin()
        ranked = rank_rollouts(rollouts)
        return {
            "ranking": [
                {
                    "plan_id": item.plan_id,
                    "microtwin_score": item.microtwin_score,
                    "advisory_score": item.advisory_score,
                    "qualification": item.qualification_status,
                }
                for item in ranked
            ]
        }, {"tie_break": "microtwin_score,plan_id"}

    def _tool_get_microtwin_rollout(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        _, _, _, rollouts = self._microtwin()
        item = next(
            (value for value in rollouts if value.rollout_id == str(arguments["rollout_id"])), None
        )
        if item is None:
            raise ValueError("unknown_rollout")
        return item.model_dump(mode="json"), {"source": "deterministic rollout"}

    def _tool_rank_plans_with_microtwin(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, _, _, rollouts = self._microtwin()
        ranked = rank_rollouts(rollouts)
        return {
            "selected_plan_id": ranked[0].plan_id,
            "ranking": [item.plan_id for item in ranked],
            "physical_write_count": 0,
            "no_write_confirmation": True,
        }, {"model_authority": "advisory_only"}

    def _ledger(self) -> tuple[Any, tuple[Any, ...], tuple[Any, ...], tuple[Any, ...], Any]:
        context, plans, _, rollouts = self._microtwin()
        ledger = load_comfort_ledger_settings(self.settings.root / "config/comfort_ledger.yaml")
        bank = load_thermal_bank_settings(self.settings.root / "config/thermal_bank.yaml")
        evaluations = evaluate_candidates(context, plans, rollouts, ledger, bank)
        ranking = rank_evaluations(context, plans, rollouts, evaluations)
        return context, plans, rollouts, evaluations, ranking

    def _tool_get_comfort_ledger_status(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, _, _, evaluations, _ = self._ledger()
        return {
            "schema_version": 1,
            "account_status": "ACTIVE",
            "current_credit": 0.0,
            "current_debt": 0.0,
            "debt_status": "NONE",
            "active_recovery_obligations": 0,
            "recent_burden_summary": {
                item.plan_id: item.new_comfort_burden for item in evaluations
            },
            "limitations": [
                "temperature-boundary proxy",
                "not subjective comfort",
                "advisory only",
            ],
        }, {"source": "schema-v8 ledger evidence"}

    def _tool_get_comfort_ledger_entries(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, _, _, evaluations, _ = self._ledger()
        rows = [entry.model_dump(mode="json") for item in evaluations for entry in item.entries]
        plan_id = arguments.get("plan_id")
        if plan_id:
            rows = [row for row in rows if row["plan_id"] == str(plan_id)]
        limit = self._limit(arguments)
        offset = (
            decode_cursor(str(arguments["cursor"]), "get_comfort_ledger_entries", None)
            if arguments.get("cursor")
            else 0
        )
        page = rows[offset : offset + limit]
        next_cursor = (
            encode_cursor("get_comfort_ledger_entries", None, offset + limit)
            if offset + limit < len(rows)
            else None
        )
        return {"entries": page, "next_cursor": next_cursor, "total": len(rows)}, {"bounded": True}

    def _ledger_evaluation(self, arguments: dict[str, Any]) -> Any:
        _, _, _, evaluations, _ = self._ledger()
        plan_id = str(arguments["plan_id"])
        item = next((value for value in evaluations if value.plan_id == plan_id), None)
        if item is None:
            raise ValueError("unknown_or_ineligible_plan")
        forbidden = {
            "closing_debt",
            "bank_balance",
            "equity_score",
            "ledger_aware_score",
        } & arguments.keys()
        if forbidden:
            raise ValueError("caller_supplied_authoritative_value")
        return item

    def _tool_evaluate_plan_comfort_ledger(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        item = self._ledger_evaluation(arguments)
        data = item.model_dump(mode="json", exclude={"entries", "bank"})
        data["no_write_confirmation"] = True
        return data, {"authority": "deterministic comfort ledger"}

    def _tool_compare_comfort_ledger_evaluations(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, _, _, evaluations, _ = self._ledger()
        return {
            "evaluations": [
                {
                    "plan_id": item.plan_id,
                    "burden": item.new_comfort_burden,
                    "closing_debt": item.closing_comfort_debt,
                    "equity_score": item.comfort_equity_score,
                    "eligible": item.eligible,
                }
                for item in evaluations
            ]
        }, {"proxy": "event and temporal"}

    def _tool_get_thermal_bank_status(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        return {
            "schema_version": 1,
            "unit": "RTFU",
            "opening_balance": 0.0,
            "deposits": 0.0,
            "withdrawals": 0.0,
            "reserves": 0.0,
            "closing_balance": 0.0,
            "limitations": ["relative advisory units", "not physical energy"],
        }, {"source": "schema-v8 bank account"}

    def _tool_get_thermal_bank_transactions(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        micro = load_microtwin_settings(self.settings.root / "config/microtwin.yaml")
        limit = self._limit(arguments)
        with sqlite3.connect(micro.database) as connection:
            connection.row_factory = sqlite3.Row
            rows = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM thermal_bank_transactions ORDER BY sequence LIMIT ?", (limit,)
                )
            ]
        return {"transactions": rows, "unit": "RTFU"}, {"bounded": True}

    def _tool_evaluate_plan_thermal_bank(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        item = self._ledger_evaluation(arguments)
        return {
            **item.bank.model_dump(mode="json"),
            "plan_id": item.plan_id,
            "physical_write_performed": False,
        }, {"unit_boundary": "relative advisory RTFU"}

    def _tool_rank_plans_with_ledger(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        _, _, _, evaluations, ranking = self._ledger()
        return {
            "selected_plan_id": ranking.selected_plan_id,
            "ranking": list(ranking.module13_ranking),
            "scores": {item.plan_id: item.ledger_aware_score for item in evaluations},
            "physical_write_count": 0,
        }, {"selection": "MODULE_13_LEDGER_SELECTION"}

    def _tool_get_ledger_ranking(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        _, _, _, _, ranking = self._ledger()
        return ranking.model_dump(mode="json"), {"disagreement_visible": True}

    def _tool_select_ledger_advisory_plan(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        _, _, _, evaluations, ranking = self._ledger()
        plan_id = str(arguments["plan_id"])
        if not any(item.plan_id == plan_id and item.eligible for item in evaluations):
            raise ValueError("invented_or_ledger_ineligible_plan")
        return {
            "selected_plan_id": plan_id,
            "authoritative_plan_id": ranking.selected_plan_id,
            "agreement": plan_id == ranking.selected_plan_id,
            "advisory_only": True,
            "physical_write_performed": False,
        }, {"no_guarded_command": True}

    def _execution_database(self) -> Path:
        return load_microtwin_settings(self.settings.root / "config/microtwin.yaml").database

    def _tool_get_execution_approval_status(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        with sqlite3.connect(self._execution_database()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT approval_id,execution_mode,plan_id,expires_at,status,consumed_session_id,"
                "approval_fingerprint FROM execution_approvals ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
        return (
            {"approval": dict(row) if row else None, "simulation_only": True},
            {"source": "schema-v9 execution evidence"},
        )

    def _tool_get_plan_execution_status(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        with sqlite3.connect(self._execution_database()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT session_id,mode,state,physical_set_calls,physical_reset_calls,"
                "fallback_count FROM execution_sessions ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
        return (
            {
                "session": dict(row) if row else None,
                "physical_simulation_only": True,
                "limitations": ["short-horizon simulation", "not real-building control"],
            },
            {"source": "schema-v9 execution evidence"},
        )

    def _tool_get_plan_execution_audit(
        self, arguments: dict[str, Any]
    ) -> tuple[Any, dict[str, Any]]:
        limit = self._limit(arguments)
        with sqlite3.connect(self._execution_database()) as connection:
            connection.row_factory = sqlite3.Row
            latest = connection.execute(
                "SELECT session_id FROM execution_sessions ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            transitions = (
                []
                if latest is None
                else [
                    dict(row)
                    for row in connection.execute(
                        "SELECT * FROM execution_state_transitions WHERE session_id=? "
                        "ORDER BY sequence LIMIT ?",
                        (latest[0], limit),
                    )
                ]
            )
            actions = (
                []
                if latest is None
                else [
                    dict(row)
                    for row in connection.execute(
                        "SELECT * FROM execution_actions WHERE session_id=? "
                        "ORDER BY action_sequence LIMIT ?",
                        (latest[0], limit),
                    )
                ]
            )
        return {"transitions": transitions, "actions": actions, "bounded": True}, {
            "read_only": True
        }

    def _tool_compare_execution_runs(self, arguments: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
        with sqlite3.connect(self._execution_database()) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM execution_run_comparisons ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
        return {
            "comparison": dict(row) if row else None,
            "claim_boundary": "short-horizon EnergyPlus simulation difference",
        }, {"read_only": True}
