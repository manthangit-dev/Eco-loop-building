from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError
from scripts.planning_common import build
from src.agent.ledger_policy import (
    LedgerClaimError,
    validate_authoritative_values,
    validate_ledger_response,
)
from src.ledger.config import ComfortLedgerSettings, load_comfort_ledger_settings
from src.ledger.errors import LedgerValidationError
from src.ledger.evaluation import evaluate_candidates, evaluate_rollout, rank_evaluations
from src.ledger.models import LedgerPlanEvaluation
from src.mcp_server.config import load_mcp_settings
from src.mcp_server.models import ToolRequest
from src.mcp_server.service import MCPToolService
from src.microtwin.config import load_microtwin_settings
from src.microtwin.rollout import PlanRollout, rollout
from src.planning.models import CandidatePlan, PlanningContext
from src.storage.ledger_schema import migrate
from src.storage.ledger_store import LedgerStore
from src.thermal_bank.accounting import closing_balance
from src.thermal_bank.config import ThermalBankSettings, load_thermal_bank_settings
from src.thermal_bank.errors import ThermalBankValidationError

ROOT = Path(__file__).resolve().parents[1]
Domain = tuple[
    PlanningContext,
    tuple[CandidatePlan, ...],
    tuple[PlanRollout, ...],
    ComfortLedgerSettings,
    ThermalBankSettings,
    tuple[LedgerPlanEvaluation, ...],
]


@pytest.fixture(scope="module")
def domain() -> Domain:
    context, plans = build()
    micro = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    rollouts = tuple(rollout(context, plan, micro) for plan in plans if plan.eligible)
    ledger = load_comfort_ledger_settings(ROOT / "config/comfort_ledger.yaml")
    bank = load_thermal_bank_settings(ROOT / "config/thermal_bank.yaml")
    evaluations = evaluate_candidates(context, plans, rollouts, ledger, bank)
    return context, plans, rollouts, ledger, bank, evaluations


def test_valid_configs() -> None:
    ledger = load_comfort_ledger_settings(ROOT / "config/comfort_ledger.yaml")
    bank = load_thermal_bank_settings(ROOT / "config/thermal_bank.yaml")
    assert ledger.schema_version == bank.schema_version == 1
    assert ledger.advisory_only and bank.advisory_only and bank.unit == "RTFU"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("schema_version", 2),
        ("advisory_only", False),
        ("occupied_upper_c", 21.0),
        ("maximum_debt", -1.0),
        ("debt_expiry_timesteps", -1),
    ),
)
def test_invalid_ledger_config(field: str, value: object) -> None:
    settings = load_comfort_ledger_settings(ROOT / "config/comfort_ledger.yaml")
    with pytest.raises((ValidationError, ValueError)):
        ComfortLedgerSettings.model_validate({**settings.model_dump(), field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("schema_version", 2),
        ("advisory_only", False),
        ("overdraft_allowed", True),
        ("maximum_balance", -1.0),
        ("deposit_expiry_timesteps", -1),
    ),
)
def test_invalid_bank_config(field: str, value: object) -> None:
    settings = load_thermal_bank_settings(ROOT / "config/thermal_bank.yaml")
    with pytest.raises((ValidationError, ValueError)):
        ThermalBankSettings.model_validate({**settings.model_dump(), field: value})


def test_all_candidate_evaluations_are_deterministic(domain: Domain) -> None:
    context, plans, rollouts, ledger, bank, evaluations = domain
    repeated = evaluate_candidates(context, plans, rollouts, ledger, bank)
    assert len(evaluations) == 5 and evaluations == repeated
    assert all(not item.physical_write_performed for item in evaluations)
    assert all(item.closing_comfort_debt >= 0 for item in evaluations)
    assert all(0 <= item.comfort_equity_score <= 100 for item in evaluations)
    assert all(item.bank.closing_balance >= 0 for item in evaluations)


def test_initial_and_existing_debt_states(domain: Domain) -> None:
    context, plans, rollouts, ledger, bank, _ = domain
    plan, item = plans[0], rollouts[0]
    clean = evaluate_rollout(context, plan, item, ledger, bank)
    moderate = evaluate_rollout(context, plan, item, ledger, bank, opening_debt=20.0)
    blocking = evaluate_rollout(context, plan, item, ledger, bank, opening_debt=45.0)
    assert clean.opening_comfort_debt == 0 and clean.opening_comfort_credit == 0
    assert moderate.debt_status in {"MODERATE", "HIGH"}
    assert blocking.debt_status == "BLOCKING" and not blocking.eligible


def test_ranking_reports_disagreement(domain: Domain) -> None:
    context, plans, rollouts, _, _, evaluations = domain
    ranking = rank_evaluations(context, plans, rollouts, evaluations)
    assert ranking.selected_plan_id in ranking.module13_ranking
    assert ranking.module11_ranking != ranking.module12_ranking
    assert ranking.physical_write_performed is False


def test_nonfinite_and_context_mutations_fail(domain: Domain) -> None:
    context, plans, rollouts, ledger, bank, _ = domain
    changed = rollouts[0].model_copy(
        update={
            "points": (
                rollouts[0].points[0].model_copy(update={"predicted_temperature_c": math.nan}),
            )
        }
    )
    with pytest.raises(LedgerValidationError, match="non_finite_ledger_input"):
        evaluate_rollout(context, plans[0], changed, ledger, bank)
    with pytest.raises(LedgerValidationError, match="plan_rollout_context_mismatch"):
        evaluate_rollout(context, plans[1], rollouts[0], ledger, bank)


def test_bank_accounting_rejects_overdraft_and_nonfinite() -> None:
    settings = load_thermal_bank_settings(ROOT / "config/thermal_bank.yaml")
    assert (
        closing_balance(
            opening=0.0,
            deposit=0.0,
            withdrawal=0.0,
            decay=0.0,
            expiry=0.0,
            debt_penalty=0.0,
            uncertainty_reserve=0.0,
            protected_event_reserve=0.0,
            settings=settings,
        )
        == 0.0
    )
    with pytest.raises(ThermalBankValidationError, match="thermal_bank_overdraft"):
        closing_balance(
            opening=0.0,
            deposit=0.0,
            withdrawal=1.0,
            decay=0.0,
            expiry=0.0,
            debt_penalty=0.0,
            uncertainty_reserve=0.0,
            protected_event_reserve=0.0,
            settings=settings,
        )
    with pytest.raises(ThermalBankValidationError, match="non_finite_bank_amount"):
        closing_balance(
            opening=0.0,
            deposit=math.inf,
            withdrawal=0.0,
            decay=0.0,
            expiry=0.0,
            debt_penalty=0.0,
            uncertainty_reserve=0.0,
            protected_event_reserve=0.0,
            settings=settings,
        )


def test_schema8_persistence_and_idempotency(tmp_path: Path, domain: Domain) -> None:
    source = load_microtwin_settings(ROOT / "config/microtwin.yaml").database
    database = tmp_path / "ledger.db"
    database.write_bytes(source.read_bytes())
    context, plans, rollouts, _, _, evaluations = domain
    ranking = rank_evaluations(context, plans, rollouts, evaluations)
    with sqlite3.connect(database) as connection:
        store = LedgerStore(connection)
        store.persist(evaluations, ranking, "SPACE3-1")
        before = connection.execute("SELECT COUNT(*) FROM ledger_plan_evaluations").fetchone()[0]
        store.persist(evaluations, ranking, "SPACE3-1")
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 8
        assert (
            connection.execute("SELECT COUNT(*) FROM ledger_plan_evaluations").fetchone()[0]
            == before
        )
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
    "tool",
    (
        "get_comfort_ledger_status",
        "get_comfort_ledger_entries",
        "compare_comfort_ledger_evaluations",
        "get_thermal_bank_status",
        "get_thermal_bank_transactions",
        "rank_plans_with_ledger",
        "get_ledger_ranking",
    ),
)
def test_ledger_read_and_rank_tools(tool: str) -> None:
    service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"), audit=False)
    response = service.call(ToolRequest(request_id=f"test-{tool}", tool_name=tool))
    assert response.success, response.errors


def test_plan_specific_and_selection_tools(domain: Domain) -> None:
    service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"), audit=False)
    plan_id = domain[5][0].plan_id
    for tool in (
        "evaluate_plan_comfort_ledger",
        "evaluate_plan_thermal_bank",
        "select_ledger_advisory_plan",
    ):
        response = service.call(
            ToolRequest(request_id=f"test-{tool}", tool_name=tool, arguments={"plan_id": plan_id})
        )
        assert response.success and response.data["physical_write_performed"] is False
    rejected = service.call(
        ToolRequest(
            request_id="invented",
            tool_name="select_ledger_advisory_plan",
            arguments={"plan_id": "f" * 64},
        )
    )
    assert not rejected.success and rejected.errors[0].code == "invalid_request"


@pytest.mark.parametrize(
    ("text", "reason"),
    (
        ("We stored 4 kWh.", "false_stored_kwh_claim"),
        ("Guaranteed comfort.", "guaranteed_comfort_claim"),
        ("Verified energy savings.", "verified_savings_claim"),
        ("The plan was executed.", "false_physical_execution_claim"),
    ),
)
def test_ledger_claim_policy(text: str, reason: str) -> None:
    with pytest.raises(LedgerClaimError, match=reason):
        validate_ledger_response(text, ())


@pytest.mark.parametrize("field", ("debt", "balance", "equity"))
def test_authoritative_value_changes_are_blocked(field: str) -> None:
    values = {
        "claimed_debt": 1.0,
        "claimed_balance": 2.0,
        "claimed_equity": 80.0,
        "actual_debt": 1.0,
        "actual_balance": 2.0,
        "actual_equity": 80.0,
    }
    values[f"claimed_{field}"] += 1.0
    with pytest.raises(LedgerClaimError):
        validate_authoritative_values(**values)


def test_migration_is_additive(domain: tuple[object, ...]) -> None:
    database = load_microtwin_settings(ROOT / "config/microtwin.yaml").database
    with sqlite3.connect(database) as connection:
        migrate(connection)
        assert connection.execute("SELECT COUNT(*) FROM microtwin_models").fetchone()[0] == 1
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 8
