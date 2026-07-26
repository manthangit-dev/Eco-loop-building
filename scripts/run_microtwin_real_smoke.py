"""Run exactly three bounded real-local-model MicroTwin sessions."""

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
from src.microtwin.config import load_microtwin_settings
from src.microtwin.rollout import rank_rollouts, rollout

from scripts.demo_common import ROOT, select_demo_run
from scripts.planning_common import build


def main() -> int:
    started = time.monotonic()
    selected = select_demo_run()
    context, plans = build()
    micro = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    chosen = rank_rollouts(tuple(rollout(context, p, micro) for p in plans if p.eligible))[0]
    settings = load_llm_settings(ROOT / "config/llm_supervisor.yaml").model_copy(
        update={
            "maximum_output_tokens": 256,
            "maximum_tool_calls": 3,
            "maximum_correction_attempts": 1,
        }
    )
    provider = LocalOpenSourceProvider(settings)
    service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"))
    specs = (
        (
            ObjectiveType.EXPLAIN_MICROTWIN_VALIDATION,
            "Call get_microtwin_validation and explain measured validation without savings claims.",
        ),
        (
            ObjectiveType.COMPARE_MICROTWIN_ROLLOUTS,
            "Call compare_microtwin_rollouts and explain only returned offline surrogate results.",
        ),
        (
            ObjectiveType.RECOMMEND_MICROTWIN_RANKED_PLAN,
            "Call rank_plans_with_microtwin and report its deterministic first candidate.",
        ),
    )
    sessions: list[dict[str, Any]] = []
    for index, (objective, prompt) in enumerate(specs, 1):
        response = Supervisor(settings, provider, service).run(
            SupervisorRequest(
                request_id=f"module12-real-{index}-{time.time_ns()}",
                objective_type=objective,
                objective_text=prompt,
                run_id=selected["run_id"],
                environment_id=selected["environment_id"],
                state_id=19345,
                zone="SPACE3-1",
                candidate_plan_ids=tuple(p.plan_id for p in plans if p.eligible),
                selected_plan_id=chosen.plan_id,
            )
        )
        sessions.append(
            {
                "objective": objective.value,
                "status": response.status,
                "tools": [step.tool_name for step in response.tool_calls],
                "execution_modes": [step.execution_mode for step in response.tool_calls],
                "correction_count": int(
                    any(
                        step.execution_mode == "SUPERVISOR_REQUIRED_PREFETCH"
                        for step in response.tool_calls
                    )
                ),
                "provider_calls": 1 + len(response.tool_calls),
                "mcp_calls": len(response.tool_calls),
                "evidence_validation": bool(response.evidence),
                "successful_tools": all(step.success for step in response.tool_calls),
                "physical_write_performed": response.physical_write_performed,
            }
        )
    provider.close()
    expected = (
        ("get_microtwin_status", "get_microtwin_validation"),
        ("compare_microtwin_rollouts",),
        ("rank_plans_with_microtwin",),
    )
    passed = all(
        s["status"] == "COMPLETED"
        and s["successful_tools"]
        and all(name in s["tools"] for name in expected[i])
        and s["evidence_validation"]
        and not s["physical_write_performed"]
        for i, s in enumerate(sessions)
    )
    report = {
        "status": "PASS" if passed else "FAIL",
        "session_count": 3,
        "sessions": sessions,
        "deterministic_plan": chosen.plan_id,
        "required_tools": [
            ["get_microtwin_status", "get_microtwin_validation"],
            ["compare_microtwin_rollouts"],
            ["rank_plans_with_microtwin"],
        ],
        "physical_write_count": 0,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }
    path = ROOT / "data/output/module_12_microtwin/real_model_smoke.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 3


if __name__ == "__main__":
    raise SystemExit(main())
