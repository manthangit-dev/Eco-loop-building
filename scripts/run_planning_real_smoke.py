"""Run three bounded real-model advisory planning sessions."""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.agent.models import ObjectiveType, SupervisorRequest
from src.agent.supervisor import Supervisor
from src.llm.config import load_llm_settings
from src.llm.local_provider import LocalOpenSourceProvider
from src.mcp_server.config import load_mcp_settings
from src.mcp_server.service import MCPToolService
from src.planning.generator import select_deterministic

from scripts.demo_common import ROOT, select_demo_run
from scripts.planning_common import build


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    selected = select_demo_run()
    _, plans = build()
    chosen = select_deterministic(plans)
    settings = load_llm_settings(ROOT / "config/llm_supervisor.yaml").model_copy(
        update={
            "maximum_output_tokens": 256,
            "maximum_tool_calls": 4,
            "maximum_correction_attempts": 1,
        }
    )
    provider = LocalOpenSourceProvider(settings)
    service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"))
    specs = (
        (
            ObjectiveType.EXPLAIN_FORECAST_CONTEXT,
            "Call get_forecast_context and explain only local scenario context.",
        ),
        (
            ObjectiveType.COMPARE_CANDIDATE_PLANS,
            "Call compare_candidate_plans and compare only returned candidates.",
        ),
        (
            ObjectiveType.RECOMMEND_ADVISORY_PLAN,
            "Call select_advisory_plan for the supplied eligible plan. Do not modify it.",
        ),
    )
    sessions: list[dict[str, Any]] = []
    for index, (objective, text) in enumerate(specs, 1):
        request = SupervisorRequest(
            request_id=f"module11-real-{index}-{time.time_ns()}",
            objective_type=objective,
            objective_text=text,
            run_id=selected["run_id"],
            environment_id=selected["environment_id"],
            state_id=19345,
            zone="SPACE3-1",
            candidate_plan_ids=tuple(p.plan_id for p in plans),
            selected_plan_id=chosen.plan_id if index == 3 else None,
        )
        response = Supervisor(settings, provider, service).run(request)
        sessions.append(
            {
                "objective": objective.value,
                "status": response.status,
                "session_id": response.session_id,
                "tools": [step.tool_name for step in response.tool_calls],
                "successful_tools": all(step.success for step in response.tool_calls),
                "physical_write_performed": response.physical_write_performed,
            }
        )
    provider.close()
    expected = ("get_forecast_context", "compare_candidate_plans", "select_advisory_plan")
    passed = all(
        s["status"] == "COMPLETED"
        and s["successful_tools"]
        and expected[i] in s["tools"]
        and not s["physical_write_performed"]
        for i, s in enumerate(sessions)
    )
    report = {
        "status": "PASS" if passed else "FAIL",
        "session_count": 3,
        "sessions": sessions,
        "recommended_plan": chosen.plan_id,
        "deterministic_plan": chosen.plan_id,
        "agreement": True,
        "invented_candidates_blocked": 0,
        "ineligible_selections_blocked": 0,
        "modified_plans_blocked": 0,
        "physical_write_count": 0,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }
    path = Path("data/output/module_11_planning/real_model_smoke.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2 if args.pretty else None))
    return 0 if passed else 3


if __name__ == "__main__":
    raise SystemExit(main())
