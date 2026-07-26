from pathlib import Path

import pytest
from scripts.demo_common import ROOT, select_demo_run
from src.mcp_server.config import load_mcp_settings
from src.mcp_server.models import ToolRequest
from src.mcp_server.service import MCPToolService
from src.planning.config import PlanningSettings, load_planning_settings
from src.planning.context import build_context
from src.planning.generator import generate_plans, select_deterministic
from src.planning.models import CandidatePlan, PlanningContext
from src.planning.validator import validate_actions

PlanningFixture = tuple[PlanningSettings, PlanningContext, tuple[CandidatePlan, ...]]


@pytest.fixture(scope="module")
def planning() -> PlanningFixture:
    selected = select_demo_run()
    settings = load_planning_settings(ROOT / "config/planning.yaml")
    context = build_context(
        settings,
        selected["run_id"],
        ROOT / selected["state_database"],
        19345,
        selected["environment_id"],
    )
    return settings, context, generate_plans(context, settings)


def test_context_is_deterministic_and_has_no_future_telemetry(
    planning: PlanningFixture,
) -> None:
    settings, context, _ = planning
    again = build_context(
        settings,
        context.run_id,
        ROOT / select_demo_run()["state_database"],
        19345,
        context.environment_id,
    )
    assert context == again
    assert context.context_fingerprint == again.context_fingerprint
    assert context.prohibited_future_source_count == 0
    assert all("telemetry" not in point.source.lower() for point in context.forecasts)


def test_required_templates_are_implemented_and_bounded(planning: PlanningFixture) -> None:
    settings, _, plans = planning
    assert set(settings.strategies) == {
        "NATIVE_HOLD",
        "COMFORT_FIRST",
        "BALANCED",
        "PRECONDITION_BEFORE_PEAK",
        "VACANCY_RELAXATION",
        "OCCUPIED_RECOVERY",
    }
    assert {p.strategy_type for p in plans} == {
        "NATIVE_HOLD",
        "COMFORT_FIRST",
        "BALANCED",
        "PRECONDITION_BEFORE_PEAK",
        "VACANCY_RELAXATION",
    }
    assert len(plans) <= settings.candidate_limit
    assert all(len(p.actions) <= settings.action_limit for p in plans)


def test_actions_are_advisory_guarded_and_scores_deterministic(
    planning: PlanningFixture,
) -> None:
    settings, context, plans = planning
    repeated = generate_plans(context, settings)
    assert plans == repeated
    assert select_deterministic(plans).plan_id == select_deterministic(repeated).plan_id
    assert all(p.first_action_guard_outcome == "ALLOW" for p in plans)
    assert all(
        a.advisory_only and a.requires_execution_time_guard_validation
        for p in plans
        for a in p.actions
    )


@pytest.mark.parametrize(
    "value,reason",
    [
        (float("nan"), "non_finite_value"),
        (float("inf"), "non_finite_value"),
        (31.0, "absolute_bound_violation"),
    ],
)
def test_invalid_values_are_rejected(
    planning: PlanningFixture, value: float, reason: str
) -> None:
    settings, context, plans = planning
    action = plans[0].actions[0].model_copy(update={"requested_value": value})
    assert reason in validate_actions(context, settings, "NATIVE_HOLD", (action,))


def test_plenum_wrong_units_and_future_authority_are_rejected(
    planning: PlanningFixture,
) -> None:
    settings, context, plans = planning
    action = plans[0].actions[0]
    wrong = action.model_copy(update={"units": "F"})
    assert "unapproved_actuator" in validate_actions(context, settings, "NATIVE_HOLD", (wrong,))
    assert "unapproved_zone" in validate_actions(
        context.model_copy(update={"target_zone": "PLENUM-1"}), settings, "NATIVE_HOLD", (action,)
    )
    unauthorized = action.model_copy(update={"requires_execution_time_guard_validation": False})
    assert "execution_authority_forbidden" in validate_actions(
        context, settings, "NATIVE_HOLD", (unauthorized,)
    )


def test_six_mcp_planning_tools_and_selection_policy(planning: PlanningFixture) -> None:
    _, _, plans = planning
    service = MCPToolService(load_mcp_settings(Path("config/mcp_server.yaml")))
    names = {item.name for item in service.registry}
    planning_names = {
        "get_forecast_context",
        "generate_candidate_plans",
        "evaluate_candidate_plan",
        "compare_candidate_plans",
        "get_planning_session",
        "select_advisory_plan",
    }
    assert planning_names <= names and len(names) == 44
    assert not service.definitions["propose_guarded_control"].enabled
    response = service.call(
        ToolRequest(
            request_id="planning-test-selection",
            tool_name="select_advisory_plan",
            arguments={"plan_id": select_deterministic(plans).plan_id},
        )
    )
    assert response.success and response.data["physical_write_performed"] is False
    invented = service.call(
        ToolRequest(
            request_id="planning-test-invented",
            tool_name="select_advisory_plan",
            arguments={"plan_id": "invented"},
        )
    )
    assert not invented.success
