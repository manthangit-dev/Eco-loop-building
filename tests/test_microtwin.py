from __future__ import annotations

import json
from pathlib import Path

import pytest
from scripts.planning_common import build
from src.mcp_server.config import load_mcp_settings
from src.mcp_server.models import ToolRequest
from src.mcp_server.service import MCPToolService
from src.microtwin.config import load_microtwin_settings
from src.microtwin.rollout import PlanRollout, rank_rollouts, rollout
from src.planning.models import CandidatePlan, PlanningContext

ROOT = Path(__file__).resolve().parents[1]


def _rollouts() -> tuple[PlanningContext, tuple[CandidatePlan, ...], tuple[PlanRollout, ...]]:
    context, plans = build()
    settings = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    return (
        context,
        plans,
        tuple(rollout(context, plan, settings) for plan in plans if plan.eligible),
    )


def test_safe_qualified_artifacts_and_chronological_split() -> None:
    model_dir = ROOT / "outputs/microtwin/models"
    manifest = json.loads((model_dir / "model_manifest.json").read_text())
    split = json.loads((model_dir / "split_manifest.json").read_text())
    report = json.loads((model_dir / "thermal_validation_report.json").read_text())
    assert manifest["thermal_qualification"] is True
    assert report["mae"] < report["persistence_mae"]
    assert split["train_end"] < split["validation_start"] < split["test_start"]
    assert all(path.suffix == ".json" for path in model_dir.iterdir())


def test_all_eligible_candidates_have_deterministic_causal_rollouts() -> None:
    context, plans, first = _rollouts()
    _, _, second = _rollouts()
    assert len(first) == sum(plan.eligible for plan in plans) == 5
    assert [item.rollout_fingerprint for item in first] == [
        item.rollout_fingerprint for item in second
    ]
    assert all(len(item.points) == context.horizon for item in first)
    assert all(item.physical_write_count == 0 for item in first)
    assert all("not EnergyPlus result" in item.assumptions for item in first)
    assert rank_rollouts(first)[0].plan_id == rank_rollouts(second)[0].plan_id


def test_ood_is_reported_and_penalised() -> None:
    context, plans, _ = _rollouts()
    settings = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    changed = context.model_copy(
        update={
            "forecasts": tuple(
                point.model_copy(update={"value": 1000.0})
                if point.forecast_type == "WEATHER"
                else point
                for point in context.forecasts
            )
        }
    )
    item = rollout(changed, next(plan for plan in plans if plan.eligible), settings)
    assert item.ood_timestep_count > 0
    assert item.score_components["ood"] > 0


def test_microtwin_mcp_surface_and_unknown_plan_rejection() -> None:
    service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"), audit=False)
    expected = {
        "get_microtwin_status",
        "get_microtwin_validation",
        "evaluate_plan_with_microtwin",
        "compare_microtwin_rollouts",
        "get_microtwin_rollout",
        "rank_plans_with_microtwin",
    }
    assert expected <= service.definitions.keys()
    assert "train_microtwin" not in service.definitions
    result = service.call(
        ToolRequest(
            request_id="unknown-plan-test",
            tool_name="evaluate_plan_with_microtwin",
            arguments={"plan_id": "invented"},
        )
    )
    assert not result.success and result.errors[0].code == "invalid_request"
    assert service.definitions["propose_guarded_control"].enabled is False


@pytest.mark.parametrize(
    "tool_name",
    [
        "get_microtwin_status",
        "get_microtwin_validation",
        "compare_microtwin_rollouts",
        "rank_plans_with_microtwin",
    ],
)
def test_microtwin_mcp_calls(tool_name: str) -> None:
    service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"), audit=False)
    result = service.call(ToolRequest(request_id=f"test-{tool_name}", tool_name=tool_name))
    assert result.success
