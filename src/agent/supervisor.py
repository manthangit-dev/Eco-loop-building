"""Bounded model-owned-by-code tool loop."""

from __future__ import annotations

import json
import time
from typing import Any

from src.agent.context_manager import enforce_budget, summarise_tool_result
from src.agent.evidence import reconcile
from src.agent.ledger_policy import validate_ledger_response
from src.agent.models import Evidence, SupervisorRequest, SupervisorResponse, ToolStep
from src.agent.policy import ToolPolicy
from src.agent.tool_parser import parse_tool_call
from src.agent.trusted_fields import trusted_control_arguments
from src.llm.config import LLMSettings
from src.llm.models import ProviderMessage
from src.llm.provider import LLMProvider
from src.mcp_server.models import ToolEnvelope, ToolRequest, fingerprint
from src.mcp_server.service import MCPToolService
from src.storage.llm_store import LLMStore

SYSTEM_POLICY = """Use only supplied local MCP tools. Never invent telemetry, savings,
comfort improvement, or physical action. Control is disabled; proposals are dry-run only.
PLENUM-1 is never controllable. Return bounded structured JSON evidence."""

REQUIRED_EVIDENCE: dict[str, tuple[str, ...]] = {
    "EXPLAIN_MICROTWIN_VALIDATION": (
        "get_microtwin_status",
        "get_microtwin_validation",
    ),
    "COMPARE_MICROTWIN_ROLLOUTS": ("compare_microtwin_rollouts",),
    "RECOMMEND_MICROTWIN_RANKED_PLAN": ("rank_plans_with_microtwin",),
    "EXPLAIN_COMFORT_LEDGER": ("get_comfort_ledger_status", "get_comfort_ledger_entries"),
    "EXPLAIN_COMFORT_DEBT": ("get_comfort_ledger_status",),
    "EXPLAIN_RECOVERY_OBLIGATION": ("get_comfort_ledger_status",),
    "COMPARE_COMFORT_LEDGER_PLANS": ("compare_comfort_ledger_evaluations",),
    "EXPLAIN_COMFORT_EQUITY_SCORE": ("compare_comfort_ledger_evaluations",),
    "EXPLAIN_THERMAL_BANK": ("get_thermal_bank_status", "evaluate_plan_thermal_bank"),
    "COMPARE_THERMAL_BANK_PLANS": ("evaluate_plan_thermal_bank",),
    "RECOMMEND_LEDGER_AWARE_PLAN": ("rank_plans_with_ledger",),
    "EXPLAIN_LEDGER_LIMITATIONS": ("get_comfort_ledger_status", "get_thermal_bank_status"),
    "EXPLAIN_EXECUTION_APPROVAL": ("get_execution_approval_status",),
    "EXPLAIN_EXECUTION_STATUS": ("get_plan_execution_status",),
    "EXPLAIN_EXECUTION_FALLBACK": ("get_plan_execution_audit",),
    "EXPLAIN_EXECUTION_AUDIT": ("get_plan_execution_audit",),
    "COMPARE_SHORT_EXECUTION_RUNS": ("compare_execution_runs",),
    "EXPLAIN_SIMULATION_RECONCILIATION": (
        "compare_execution_runs",
        "get_microtwin_rollout",
    ),
}


def _session_id(request: SupervisorRequest) -> str:
    payload = request.model_dump(mode="json")
    if not request.candidate_plan_ids:
        payload.pop("candidate_plan_ids", None)
    if request.selected_plan_id is None:
        payload.pop("selected_plan_id", None)
    return fingerprint(payload)


class Supervisor:
    def __init__(self, settings: LLMSettings, provider: LLMProvider, tools: MCPToolService) -> None:
        self.settings, self.provider, self.tools = settings, provider, tools
        self.policy = ToolPolicy(tools.registry)

    def run(self, request: SupervisorRequest) -> SupervisorResponse:
        with LLMStore(self.settings.database, self.settings.output_root) as store:
            response = self._run(request)
            return store.append(
                request,
                response,
                self.tools.catalogue_fingerprint,
                self.settings.prompt_template_version,
            )

    def _run(self, request: SupervisorRequest) -> SupervisorResponse:
        session_id = _session_id(request)
        started = time.monotonic()
        messages = [
            ProviderMessage(role="system", content=SYSTEM_POLICY),
            ProviderMessage(role="user", content=request.model_dump_json()),
        ]
        seen: set[str] = set()
        results: dict[str, ToolEnvelope] = {}
        steps: list[ToolStep] = []
        corrections = 0
        evidence_correction_used = False
        prefetch_used = False
        for iteration in range(self.settings.maximum_supervisor_iterations):
            if time.monotonic() - started > self.settings.session_timeout_seconds:
                return self._failure(request, session_id, "session_timeout", steps)
            context = enforce_budget(messages, self.settings.maximum_input_tokens)
            output = self.provider.generate_with_tools(context, self._catalogue(request))
            try:
                call = parse_tool_call(output)
            except (ValueError, json.JSONDecodeError) as exc:
                corrections += 1
                if corrections > self.settings.maximum_correction_attempts:
                    return self._failure(request, session_id, str(exc), steps)
                messages.append(ProviderMessage(role="user", content=f"CORRECT:{exc}"))
                continue
            if call is None:
                missing = self._missing_required_evidence(request, steps)
                if missing and not evidence_correction_used:
                    evidence_correction_used = True
                    corrections += 1
                    messages.append(
                        ProviderMessage(
                            role="user",
                            content=(
                                "required_tool_evidence_missing: call these permitted tools "
                                f"before answering: {', '.join(missing)}"
                            ),
                        )
                    )
                    continue
                if missing and not prefetch_used:
                    prefetch_used = True
                    for name in missing:
                        result = self._execute_required_prefetch(
                            request, session_id, iteration, name, steps
                        )
                        results[result.tool_call_id] = result
                        messages.append(
                            ProviderMessage(
                                role="tool",
                                content=summarise_tool_result(
                                    result.model_dump(mode="json"),
                                    self.settings.maximum_tool_result_characters,
                                ),
                            )
                        )
                    messages.append(
                        ProviderMessage(
                            role="user",
                            content=(
                                "Authoritative required evidence was prefetched by the supervisor. "
                                "Interpret it without inventing claims."
                            ),
                        )
                    )
                    continue
                if missing:
                    return self._failure(
                        request, session_id, "required_tool_evidence_missing", steps
                    )
                return self._final(request, output.text, steps, results)
            call = self._canonicalise_request_bound_call(request, call)
            if len(steps) >= self.settings.maximum_tool_calls:
                return self._failure(request, session_id, "tool_call_limit", steps)
            canonical = fingerprint({"name": call.name, "arguments": call.arguments})
            if canonical in seen:
                return self._failure(request, session_id, "repeated_tool_call", steps)
            seen.add(canonical)
            try:
                self.policy.validate(call.name, call.arguments)
            except (ValueError, PermissionError) as exc:
                return self._failure(request, session_id, str(exc), steps)
            tool_request = ToolRequest(
                request_id=f"{session_id[:16]}-{iteration}",
                tool_name=call.name,
                arguments=call.arguments,
            )
            result = self.tools.call(tool_request)
            results[result.tool_call_id] = result
            steps.append(
                ToolStep(
                    tool_name=call.name,
                    tool_call_id=result.tool_call_id,
                    success=result.success,
                    execution_mode="MODEL_SELECTED_TOOL",
                )
            )
            summary = summarise_tool_result(
                result.model_dump(mode="json"), self.settings.maximum_tool_result_characters
            )
            messages.append(ProviderMessage(role="tool", content=summary))
        return self._failure(request, session_id, "iteration_limit", steps)

    @staticmethod
    def _missing_required_evidence(
        request: SupervisorRequest, steps: list[ToolStep]
    ) -> tuple[str, ...]:
        required = REQUIRED_EVIDENCE.get(request.objective_type.value, ())
        successful = {step.tool_name for step in steps if step.success}
        return tuple(name for name in required if name not in successful)

    def _execute_required_prefetch(
        self,
        request: SupervisorRequest,
        session_id: str,
        iteration: int,
        name: str,
        steps: list[ToolStep],
    ) -> ToolEnvelope:
        if name not in self.policy.allowed_names:
            raise PermissionError("required_tool_not_permitted")
        arguments: dict[str, Any] = {}
        if name in {"evaluate_plan_thermal_bank", "evaluate_plan_comfort_ledger"}:
            plan_id = request.selected_plan_id or next(iter(request.candidate_plan_ids), None)
            if plan_id is None:
                raise ValueError("required_plan_id_missing")
            arguments = {"plan_id": plan_id}
        tool_request = ToolRequest(
            request_id=f"{session_id[:16]}-prefetch-{iteration}-{len(steps)}",
            tool_name=name,
            arguments=arguments,
        )
        result = self.tools.call(tool_request)
        steps.append(
            ToolStep(
                tool_name=name,
                tool_call_id=result.tool_call_id,
                success=result.success,
                execution_mode="SUPERVISOR_REQUIRED_PREFETCH",
            )
        )
        return result

    def _canonicalise_request_bound_call(self, request: SupervisorRequest, call: Any) -> Any:
        """Replace schema-constant fields with trusted request values after model selection."""
        from src.llm.models import ModelToolCall

        if call.name == "get_building_state":
            return ModelToolCall(
                name=call.name, arguments={"run_id": request.run_id, "state_id": request.state_id}
            )
        if call.name == "get_safety_guard_status":
            return ModelToolCall(name=call.name, arguments={})
        if call.name in {
            "get_microtwin_status",
            "get_microtwin_validation",
            "compare_microtwin_rollouts",
            "rank_plans_with_microtwin",
        }:
            return ModelToolCall(name=call.name, arguments={})
        if call.name == "evaluate_plan_with_microtwin":
            if request.selected_plan_id not in request.candidate_plan_ids:
                raise ValueError("ineligible_or_invented_candidate")
            return ModelToolCall(name=call.name, arguments={"plan_id": request.selected_plan_id})
        if call.name in {
            "get_forecast_context",
            "generate_candidate_plans",
            "compare_candidate_plans",
        }:
            return ModelToolCall(
                name=call.name,
                arguments={
                    "run_id": request.run_id,
                    "environment_id": request.environment_id,
                    "source_state_id": request.state_id,
                    "zone": request.zone or "SPACE3-1",
                    "horizon": 12,
                },
            )
        if call.name == "select_advisory_plan":
            if request.selected_plan_id not in request.candidate_plan_ids:
                raise ValueError("ineligible_or_invented_candidate")
            return ModelToolCall(
                name=call.name,
                arguments={
                    "run_id": request.run_id,
                    "environment_id": request.environment_id,
                    "source_state_id": request.state_id,
                    "zone": request.zone or "SPACE3-1",
                    "horizon": 12,
                    "plan_id": request.selected_plan_id,
                },
            )
        if (
            call.name == "validate_control_proposal"
            and request.objective_type.value == "ASSESS_CONTROL_PROPOSAL_DRY_RUN"
        ):
            return ModelToolCall(name=call.name, arguments=trusted_control_arguments(request))
        return call

    def _catalogue(self, request: SupervisorRequest) -> tuple[dict[str, Any], ...]:
        mapping = {
            "DESCRIBE_CURRENT_STATE": ("get_building_state",),
            "EXPLAIN_SAFETY_STATUS": ("get_safety_guard_status",),
            "ASSESS_CONTROL_PROPOSAL_DRY_RUN": ("validate_control_proposal",),
            "EXPLAIN_FORECAST_CONTEXT": ("get_forecast_context",),
            "GENERATE_CANDIDATE_PLANS": ("generate_candidate_plans",),
            "COMPARE_CANDIDATE_PLANS": ("compare_candidate_plans",),
            "RECOMMEND_ADVISORY_PLAN": ("select_advisory_plan",),
            "EXPLAIN_MICROTWIN_STATUS": ("get_microtwin_status",),
            "EXPLAIN_MICROTWIN_VALIDATION": (
                "get_microtwin_status",
                "get_microtwin_validation",
            ),
            "EVALUATE_PLAN_WITH_MICROTWIN": ("evaluate_plan_with_microtwin",),
            "COMPARE_MICROTWIN_ROLLOUTS": ("compare_microtwin_rollouts",),
            "RECOMMEND_MICROTWIN_RANKED_PLAN": ("rank_plans_with_microtwin",),
            "EXPLAIN_RANKING_DIFFERENCE": ("compare_microtwin_rollouts",),
            "EXPLAIN_MICROTWIN_UNCERTAINTY": ("compare_microtwin_rollouts",),
            "EXPLAIN_COMFORT_LEDGER": (
                "get_comfort_ledger_status",
                "get_comfort_ledger_entries",
            ),
            "EXPLAIN_COMFORT_DEBT": ("get_comfort_ledger_status",),
            "EXPLAIN_RECOVERY_OBLIGATION": ("get_comfort_ledger_status",),
            "COMPARE_COMFORT_LEDGER_PLANS": ("compare_comfort_ledger_evaluations",),
            "EXPLAIN_COMFORT_EQUITY_SCORE": ("compare_comfort_ledger_evaluations",),
            "EXPLAIN_THERMAL_BANK": ("get_thermal_bank_status",),
            "COMPARE_THERMAL_BANK_PLANS": ("evaluate_plan_thermal_bank",),
            "RECOMMEND_LEDGER_AWARE_PLAN": ("rank_plans_with_ledger",),
            "EXPLAIN_LEDGER_LIMITATIONS": (
                "get_comfort_ledger_status",
                "get_thermal_bank_status",
            ),
            "EXPLAIN_EXECUTION_APPROVAL": ("get_execution_approval_status",),
            "EXPLAIN_EXECUTION_STATUS": ("get_plan_execution_status",),
            "EXPLAIN_EXECUTION_FALLBACK": ("get_plan_execution_audit",),
            "EXPLAIN_EXECUTION_AUDIT": ("get_plan_execution_audit",),
            "COMPARE_SHORT_EXECUTION_RUNS": ("compare_execution_runs",),
            "EXPLAIN_SIMULATION_RECONCILIATION": (
                "compare_execution_runs",
                "get_microtwin_rollout",
            ),
        }
        if "propose_guarded_control" in request.objective_text:
            names: tuple[str, ...] = ()
        else:
            names = mapping.get(request.objective_type.value, self.policy.allowed_names)
        schemas: dict[str, dict[str, Any]] = {
            "get_building_state": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "const": request.run_id},
                    "state_id": {"type": "integer", "const": request.state_id},
                },
                "required": ["run_id", "state_id"],
                "additionalProperties": False,
            },
            "get_safety_guard_status": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "get_forecast_context": self._planning_schema(request),
            "generate_candidate_plans": self._planning_schema(request),
            "compare_candidate_plans": self._planning_schema(request),
            "select_advisory_plan": self._planning_schema(request, include_plan=True),
            "get_microtwin_status": self._empty_schema(),
            "get_microtwin_validation": self._empty_schema(),
            "compare_microtwin_rollouts": self._empty_schema(),
            "rank_plans_with_microtwin": self._empty_schema(),
            "get_comfort_ledger_status": self._empty_schema(),
            "get_comfort_ledger_entries": self._empty_schema(),
            "compare_comfort_ledger_evaluations": self._empty_schema(),
            "get_thermal_bank_status": self._empty_schema(),
            "rank_plans_with_ledger": self._empty_schema(),
            "evaluate_plan_thermal_bank": {
                "type": "object",
                "properties": {
                    "plan_id": {"type": "string", "enum": list(request.candidate_plan_ids)}
                },
                "required": ["plan_id"],
                "additionalProperties": False,
            },
            "evaluate_plan_with_microtwin": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "enum": list(request.candidate_plan_ids),
                    }
                },
                "required": ["plan_id"],
                "additionalProperties": False,
            },
            "validate_control_proposal": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string", "const": request.run_id},
                    "environment_id": {"type": "string", "const": request.environment_id},
                    "source_state_sequence": {"type": "integer", "const": request.state_id},
                    "current_sequence": {
                        "type": "integer",
                        "const": None if request.state_id is None else request.state_id + 1,
                    },
                    "component_type": {"type": "string", "const": "Zone Temperature Control"},
                    "control_type": {"type": "string", "const": "Cooling Setpoint"},
                    "actuator_key": {"type": "string", "const": request.zone or "SPACE3-1"},
                    "zone": {"type": "string", "const": request.zone or "SPACE3-1"},
                    "units": {"type": "string", "const": request.proposal_units or "C"},
                    "requested_value": {"type": "number", "const": request.proposal_value},
                    "client_request_id": {"type": "string", "const": request.request_id},
                },
                "required": [
                    "run_id",
                    "environment_id",
                    "source_state_sequence",
                    "current_sequence",
                    "component_type",
                    "control_type",
                    "actuator_key",
                    "zone",
                    "units",
                    "requested_value",
                    "client_request_id",
                ],
                "additionalProperties": False,
            },
        }
        return tuple(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": self.tools.definitions[name].purpose,
                    "parameters": schemas.get(name, {"type": "object"}),
                },
            }
            for name in names
            if name in self.policy.allowed_names
        )

    @staticmethod
    def _empty_schema() -> dict[str, Any]:
        return {"type": "object", "properties": {}, "additionalProperties": False}

    def _planning_schema(
        self, request: SupervisorRequest, *, include_plan: bool = False
    ) -> dict[str, Any]:
        properties: dict[str, Any] = {
            "run_id": {"type": "string", "const": request.run_id},
            "environment_id": {"type": "string", "const": request.environment_id},
            "source_state_id": {"type": "integer", "const": request.state_id},
            "zone": {"type": "string", "const": request.zone or "SPACE3-1"},
            "horizon": {"type": "integer", "const": 12},
        }
        if include_plan:
            properties["plan_id"] = {"type": "string", "enum": list(request.candidate_plan_ids)}
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

    def _final(
        self,
        request: SupervisorRequest,
        text: str,
        steps: list[ToolStep],
        results: dict[str, ToolEnvelope],
    ) -> SupervisorResponse:
        summary = text.strip() or "No model summary was supplied."
        evidence = tuple(
            Evidence(
                tool_name=result.tool_name,
                tool_call_id=result.tool_call_id,
                run_id=result.run_id,
                metric="structured_tool_result",
                observed_value=result.data,
                provenance=result.provenance,
            )
            for result in results.values()
            if result.success
        )
        reconcile(evidence, results)
        if "LEDGER" in request.objective_type.value or request.objective_type.value in {
            "EXPLAIN_THERMAL_BANK",
            "COMPARE_THERMAL_BANK_PLANS",
        }:
            validate_ledger_response(summary, tuple(results.values()))
        return SupervisorResponse(
            session_id=_session_id(request),
            request_id=request.request_id,
            objective_type=request.objective_type,
            status="COMPLETED",
            summary=summary,
            evidence=evidence,
            tool_calls=tuple(steps),
            limitations=("Recorded evidence only", "Physical control disabled"),
            recommended_next_step="Review recorded evidence; do not infer savings.",
            provider=self.provider.name,
            model=self.provider.model,
        )

    def _failure(
        self,
        request: SupervisorRequest,
        session_id: str,
        reason: str,
        steps: list[ToolStep],
    ) -> SupervisorResponse:
        return SupervisorResponse(
            session_id=session_id,
            request_id=request.request_id,
            objective_type=request.objective_type,
            status="FAILED_CLOSED",
            summary=f"Supervisor stopped safely: {reason}",
            tool_calls=tuple(steps),
            warnings=(reason,),
            limitations=("No physical write was possible",),
            recommended_next_step="Correct the bounded request or inspect local runtime.",
            provider=self.provider.name,
            model=self.provider.model,
        )
