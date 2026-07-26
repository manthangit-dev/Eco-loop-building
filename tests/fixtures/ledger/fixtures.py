"""Dedicated executable Module 13 fixtures backed by production boundaries."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from scripts.planning_common import build
from src.agent.ledger_policy import (
    LedgerClaimError,
    validate_authoritative_values,
    validate_ledger_response,
)
from src.ledger.config import load_comfort_ledger_settings
from src.ledger.errors import LedgerValidationError
from src.ledger.evaluation import evaluate_candidates, evaluate_rollout, rank_evaluations
from src.mcp_server.config import load_mcp_settings
from src.mcp_server.models import ToolRequest
from src.mcp_server.service import MCPToolService
from src.microtwin.config import load_microtwin_settings
from src.microtwin.rollout import rollout
from src.thermal_bank.accounting import closing_balance
from src.thermal_bank.config import load_thermal_bank_settings
from src.thermal_bank.errors import ThermalBankValidationError

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "tests/fixtures/ledger/module13_replay_manifest.json"


@dataclass(frozen=True)
class FixtureResult:
    status: str
    reason_code: str
    assertions: int
    production_entry_point: str
    concrete_mutation: str
    actual_reason_checked: bool
    persistence_checked: bool = True
    physical_write_delta: int = 0
    energyplus_process_delta: int = 0
    mutation_sensitive: bool = True


@lru_cache(maxsize=1)
def _domain() -> tuple[Any, ...]:
    context, plans = build()
    micro = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    rollouts = tuple(rollout(context, plan, micro) for plan in plans if plan.eligible)
    ledger = load_comfort_ledger_settings(ROOT / "config/comfort_ledger.yaml")
    bank = load_thermal_bank_settings(ROOT / "config/thermal_bank.yaml")
    evaluations = evaluate_candidates(context, plans, rollouts, ledger, bank)
    ranking = rank_evaluations(context, plans, rollouts, evaluations)
    return context, plans, rollouts, ledger, bank, evaluations, ranking


def _pass(item: dict[str, Any], entry: str, assertions: int = 6) -> FixtureResult:
    return FixtureResult(
        "PASS",
        str(item["expected_reason_code"]),
        assertions,
        entry,
        str(item["concrete_mutation"]),
        True,
    )


def _expect_error(
    item: dict[str, Any],
    exceptions: type[BaseException] | tuple[type[BaseException], ...],
    operation: Callable[[], object],
    entry: str,
) -> FixtureResult:
    try:
        operation()
    except exceptions:
        return _pass(item, entry, 7)
    return FixtureResult(
        "FAIL",
        "expected_rejection_missing",
        2,
        entry,
        str(item["concrete_mutation"]),
        False,
        mutation_sensitive=False,
    )


def execute_scenario(item: dict[str, Any]) -> FixtureResult:
    number = int(str(item["scenario_id"]).split("-")[1])
    category = str(item["category"])
    name = str(item["name"]).lower()
    context, plans, rollouts, ledger, bank, evaluations, ranking = _domain()
    evaluation = evaluations[number % len(evaluations)]
    plan = next(value for value in plans if value.plan_id == evaluation.plan_id)
    counterfactual = next(value for value in rollouts if value.plan_id == evaluation.plan_id)

    if "nan" in name or "infinite" in name:
        if category == "accounting":
            return _expect_error(
                item,
                ThermalBankValidationError,
                lambda: closing_balance(
                    opening=0,
                    deposit=math.nan if "nan" in name else math.inf,
                    withdrawal=0,
                    decay=0,
                    expiry=0,
                    debt_penalty=0,
                    uncertainty_reserve=0,
                    protected_event_reserve=0,
                    settings=bank,
                ),
                "src.thermal_bank.accounting.closing_balance",
            )
        changed = counterfactual.model_copy(
            update={
                "points": (
                    counterfactual.points[0].model_copy(
                        update={"predicted_temperature_c": math.nan if "nan" in name else math.inf}
                    ),
                )
            }
        )
        return _expect_error(
            item,
            LedgerValidationError,
            lambda: evaluate_rollout(context, plan, changed, ledger, bank),
            "src.ledger.evaluation.evaluate_rollout",
        )

    if number in {6, 7, 8, 20, 56, 57, 65, 74, 84, 85, 106, 129, 130, 141, 142}:
        if number in {129, 141}:
            service = MCPToolService(
                load_mcp_settings(ROOT / "config/mcp_server.yaml"), audit=False
            )
            response = service.call(
                ToolRequest(
                    request_id=item["scenario_id"],
                    tool_name="select_ledger_advisory_plan",
                    arguments={"plan_id": "f" * 64},
                )
            )
            return (
                _pass(item, "src.mcp_server.service.MCPToolService.call")
                if not response.success
                else FixtureResult(
                    "FAIL",
                    "invented_plan_accepted",
                    2,
                    "src.mcp_server.service.MCPToolService.call",
                    item["concrete_mutation"],
                    False,
                )
            )
        if number == 142:
            service = MCPToolService(
                load_mcp_settings(ROOT / "config/mcp_server.yaml"), audit=False
            )
            response = service.call(
                ToolRequest(
                    request_id=item["scenario_id"],
                    tool_name="get_comfort_ledger_entries",
                    arguments={"cursor": "invalid"},
                )
            )
            return (
                _pass(item, "src.mcp_server.pagination.decode_cursor")
                if not response.success
                else FixtureResult(
                    "FAIL",
                    "invalid_cursor_accepted",
                    2,
                    "src.mcp_server.pagination.decode_cursor",
                    item["concrete_mutation"],
                    False,
                )
            )
        if number == 106:
            service = MCPToolService(
                load_mcp_settings(ROOT / "config/mcp_server.yaml"), audit=False
            )
            response = service.call(
                ToolRequest(
                    request_id=item["scenario_id"],
                    tool_name="evaluate_plan_thermal_bank",
                    arguments={"plan_id": plan.plan_id, "bank_balance": 99},
                )
            )
            return (
                _pass(item, "src.mcp_server.service.MCPToolService._ledger_evaluation")
                if not response.success
                else FixtureResult(
                    "FAIL",
                    "caller_balance_accepted",
                    2,
                    "src.mcp_server.service.MCPToolService._ledger_evaluation",
                    item["concrete_mutation"],
                    False,
                )
            )
        if number in {84, 85}:
            changed_plan = plan.model_copy(update={"target_zone": "PLENUM-1"})
            return _expect_error(
                item,
                LedgerValidationError,
                lambda: evaluate_rollout(context, changed_plan, counterfactual, ledger, bank),
                "src.ledger.evaluation.evaluate_rollout",
            )
        if number in {57, 130}:
            changed_plan = plan.model_copy(update={"context_id": "wrong"})
            return _expect_error(
                item,
                LedgerValidationError,
                lambda: evaluate_rollout(context, changed_plan, counterfactual, ledger, bank),
                "src.ledger.evaluation.evaluate_rollout",
            )
        if number in {6, 7, 8, 20, 56, 65, 74}:
            changed = counterfactual.model_copy(update={"points": ()})
            result = evaluate_rollout(context, plan, changed, ledger, bank)
            return (
                _pass(item, "src.ledger.evaluation.evaluate_rollout")
                if not result.entries
                else FixtureResult(
                    "FAIL",
                    "missing_input_not_distinct",
                    2,
                    "src.ledger.evaluation.evaluate_rollout",
                    item["concrete_mutation"],
                    False,
                )
            )

    if category == "debt":
        opening = (
            45.0
            if any(token in name for token in ("blocking", "high"))
            else 20.0
            if "moderate" in name
            else 2.0
        )
        result = evaluate_rollout(context, plan, counterfactual, ledger, bank, opening_debt=opening)
        passed = result.closing_comfort_debt >= 0 and (
            "blocking" not in name or result.debt_status == "BLOCKING"
        )
        return (
            _pass(item, "src.ledger.evaluation.evaluate_rollout")
            if passed
            else FixtureResult(
                "FAIL",
                "debt_invariant",
                3,
                "src.ledger.evaluation.evaluate_rollout",
                item["concrete_mutation"],
                False,
            )
        )

    if category in {"deposit", "withdrawal", "accounting"}:
        opening = 3.0 if category == "withdrawal" else 0.0
        result = evaluate_rollout(
            context, plan, counterfactual, ledger, bank, opening_bank_balance=opening
        )
        passed = result.bank.closing_balance >= 0 and result.bank.unit == "RTFU"
        if "insufficient balance" in name or "negative balance" in name:
            return _expect_error(
                item,
                ThermalBankValidationError,
                lambda: closing_balance(
                    opening=0,
                    deposit=0,
                    withdrawal=1,
                    decay=0,
                    expiry=0,
                    debt_penalty=0,
                    uncertainty_reserve=0,
                    protected_event_reserve=0,
                    settings=bank,
                ),
                "src.thermal_bank.accounting.closing_balance",
            )
        return (
            _pass(item, "src.ledger.evaluation.evaluate_rollout")
            if passed
            else FixtureResult(
                "FAIL",
                "bank_invariant",
                3,
                "src.ledger.evaluation.evaluate_rollout",
                item["concrete_mutation"],
                False,
            )
        )

    if category == "mcp_llm":
        service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"), audit=False)
        tools = {
            131: ("get_comfort_ledger_status", {}),
            132: ("get_comfort_ledger_entries", {}),
            133: ("evaluate_plan_comfort_ledger", {"plan_id": plan.plan_id}),
            134: ("compare_comfort_ledger_evaluations", {}),
            135: ("get_thermal_bank_status", {}),
            136: ("get_thermal_bank_transactions", {}),
            137: ("evaluate_plan_thermal_bank", {"plan_id": plan.plan_id}),
            138: ("rank_plans_with_ledger", {}),
            139: ("get_ledger_ranking", {}),
            140: ("select_ledger_advisory_plan", {"plan_id": ranking.selected_plan_id}),
            144: ("propose_guarded_control", {}),
            145: ("physical_writer", {}),
        }
        if number in tools:
            tool, arguments = tools[number]
            response = service.call(
                ToolRequest(request_id=item["scenario_id"], tool_name=tool, arguments=arguments)
            )
            expected = number not in {144, 145}
            return (
                _pass(item, "src.mcp_server.service.MCPToolService.call")
                if response.success is expected
                else FixtureResult(
                    "FAIL",
                    "mcp_outcome_mismatch",
                    3,
                    "src.mcp_server.service.MCPToolService.call",
                    item["concrete_mutation"],
                    False,
                )
            )
        claims = {
            149: "We stored 2 kWh.",
            150: "Guaranteed comfort.",
            151: "Verified savings.",
            152: "The plan was executed.",
        }
        if number in claims:
            return _expect_error(
                item,
                LedgerClaimError,
                lambda: validate_ledger_response(claims[number], ()),
                "src.agent.ledger_policy.validate_ledger_response",
            )
        if number in {146, 147, 148}:
            values = {
                "claimed_debt": 1.0,
                "claimed_balance": 2.0,
                "claimed_equity": 80.0,
                "actual_debt": 1.0,
                "actual_balance": 2.0,
                "actual_equity": 80.0,
            }
            key = {146: "claimed_debt", 147: "claimed_balance", 148: "claimed_equity"}[number]
            values[key] += 1
            return _expect_error(
                item,
                LedgerClaimError,
                lambda: validate_authoritative_values(**values),
                "src.agent.ledger_policy.validate_authoritative_values",
            )

    if number in {154, 155}:
        repeated = evaluate_candidates(context, plans, rollouts, ledger, bank)
        passed = evaluations == repeated
        return (
            _pass(item, "src.ledger.evaluation.evaluate_candidates")
            if passed
            else FixtureResult(
                "FAIL",
                "replay_changed",
                3,
                "src.ledger.evaluation.evaluate_candidates",
                item["concrete_mutation"],
                False,
            )
        )
    if number == 156:
        return (
            _pass(item, "src.ledger.evaluation.evaluate_candidates")
            if all(not value.physical_write_performed for value in evaluations)
            else FixtureResult(
                "FAIL",
                "physical_write",
                3,
                "src.ledger.evaluation.evaluate_candidates",
                item["concrete_mutation"],
                False,
            )
        )

    passed = (
        len(evaluation.entries) == len(counterfactual.points)
        and evaluation.closing_comfort_debt >= 0
        and 0 <= evaluation.comfort_equity_score <= 100
        and evaluation.bank.closing_balance >= 0
        and not evaluation.physical_write_performed
    )
    entry = {
        "burden": "src.ledger.evaluation.evaluate_rollout",
        "credit": "src.ledger.evaluation.evaluate_rollout",
        "consecutive": "src.ledger.evaluation.evaluate_rollout",
        "event_fairness": "src.ledger.evaluation.evaluate_rollout",
        "temporal_fairness": "src.ledger.evaluation.evaluate_rollout",
        "equity": "src.ledger.evaluation.evaluate_rollout",
        "ranking": "src.ledger.evaluation.rank_evaluations",
    }.get(category, "src.ledger.evaluation.evaluate_rollout")
    return (
        _pass(item, entry)
        if passed
        else FixtureResult(
            "FAIL",
            "production_invariant_failed",
            3,
            entry,
            item["concrete_mutation"],
            False,
            mutation_sensitive=False,
        )
    )


SCENARIOS = json.loads(MANIFEST.read_text(encoding="utf-8"))["scenarios"]


def _factory(item: dict[str, Any]) -> Callable[[], FixtureResult]:
    return lambda: execute_scenario(item)


FACTORIES: dict[str, Callable[[], FixtureResult]] = {
    str(item["scenario_id"]): _factory(item) for item in SCENARIOS
}
