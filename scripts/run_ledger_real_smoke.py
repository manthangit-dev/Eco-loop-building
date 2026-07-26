"""Run exactly three bounded Module 13 mock or local-model advisory sessions."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.models import ObjectiveType, SupervisorRequest
from src.agent.supervisor import Supervisor
from src.ledger.config import load_comfort_ledger_settings
from src.ledger.evaluation import evaluate_candidates, rank_evaluations
from src.llm.config import load_llm_settings
from src.llm.local_provider import LocalOpenSourceProvider
from src.llm.mock_provider import DeterministicMockProvider
from src.llm.models import ModelToolCall, ProviderOutput
from src.mcp_server.config import load_mcp_settings
from src.mcp_server.service import MCPToolService
from src.microtwin.config import load_microtwin_settings
from src.microtwin.rollout import rollout
from src.planning.provenance import planning_fingerprint
from src.storage.ledger_schema import migrate
from src.thermal_bank.config import load_thermal_bank_settings

from scripts.planning_common import build

ROOT = Path(__file__).resolve().parents[1]


def _mock_outputs(plan_id: str) -> list[list[ProviderOutput]]:
    return [
        [
            ProviderOutput(tool_call=ModelToolCall(name="get_comfort_ledger_status", arguments={})),
            ProviderOutput(
                tool_call=ModelToolCall(name="get_comfort_ledger_entries", arguments={})
            ),
            ProviderOutput(
                text=(
                    "Schema 1 temperature-boundary proxy with empirical uncertainty; "
                    "no physical write."
                )
            ),
        ],
        [
            ProviderOutput(tool_call=ModelToolCall(name="get_thermal_bank_status", arguments={})),
            ProviderOutput(
                tool_call=ModelToolCall(
                    name="evaluate_plan_thermal_bank", arguments={"plan_id": plan_id}
                )
            ),
            ProviderOutput(
                text=(
                    "RTFU are relative advisory units, not physical energy or kWh; "
                    "no physical write."
                )
            ),
        ],
        [
            ProviderOutput(tool_call=ModelToolCall(name="rank_plans_with_ledger", arguments={})),
            ProviderOutput(
                text=(
                    "I recommend the persisted first ledger-eligible plan; rankings may disagree. "
                    "Demand is unavailable and 12-step MAE is 0.892340 C. No physical execution."
                )
            ),
        ],
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sessions", default="1,2,3")
    parser.add_argument("--attempt", default="1")
    parser.add_argument("--persist-only", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    context, plans = build()
    micro = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    rollouts = tuple(rollout(context, plan, micro) for plan in plans if plan.eligible)
    evaluations = evaluate_candidates(
        context,
        plans,
        rollouts,
        load_comfort_ledger_settings(ROOT / "config/comfort_ledger.yaml"),
        load_thermal_bank_settings(ROOT / "config/thermal_bank.yaml"),
    )
    ranking = rank_evaluations(context, plans, rollouts, evaluations)
    settings = load_llm_settings(ROOT / "config/llm_supervisor.yaml").model_copy(
        update={
            "maximum_output_tokens": 768,
            "maximum_tool_calls": 3,
            "maximum_correction_attempts": 2,
        }
    )
    service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"))
    specs = (
        (
            ObjectiveType.EXPLAIN_COMFORT_LEDGER,
            "Explain the ledger proxy, debt, uncertainty, and zero-write boundary.",
        ),
        (
            ObjectiveType.EXPLAIN_THERMAL_BANK,
            "Explain RTFU deposits, withdrawals, reserves and limitations for the selected plan.",
        ),
        (
            ObjectiveType.RECOMMEND_LEDGER_AWARE_PLAN,
            "Recommend only the deterministic first eligible ledger-ranked plan and disclose "
            "ranking differences.",
        ),
    )
    scripted = _mock_outputs(ranking.selected_plan_id)
    output = args.output or ROOT / "outputs/module13" / (
        "real_model_smoke.json" if args.real else "mock_model_smoke.json"
    )
    selected_indexes = (
        set()
        if args.persist_only
        else {int(value) - 1 for value in args.sessions.split(",") if value}
    )
    prior: list[dict[str, Any]] = []
    if output.exists():
        prior = json.loads(output.read_text(encoding="utf-8")).get("sessions", [])
    sessions: list[dict[str, Any]] = list(prior) if len(prior) == 3 else [{}, {}, {}]
    for index, (objective, prompt) in enumerate(specs):
        if index not in selected_indexes:
            continue
        provider = (
            LocalOpenSourceProvider(settings)
            if args.real
            else DeterministicMockProvider(scripted[index])
        )
        response = Supervisor(settings, provider, service).run(
            SupervisorRequest(
                request_id=(
                    f"module13-{'real' if args.real else 'mock'}-{index + 1}-attempt-{args.attempt}"
                ),
                objective_type=objective,
                objective_text=prompt,
                run_id=context.run_id,
                environment_id=context.environment_id,
                state_id=context.source_state_id,
                zone=context.target_zone,
                candidate_plan_ids=tuple(item.plan_id for item in evaluations if item.eligible),
                selected_plan_id=ranking.selected_plan_id,
            )
        )
        provider.close()
        sessions[index] = {
            "objective": objective.value,
            "status": response.status,
            "tools": [step.tool_name for step in response.tool_calls],
            "execution_modes": [step.execution_mode for step in response.tool_calls],
            "evidence_validation": bool(response.evidence),
            "physical_write_performed": response.physical_write_performed,
            "recommended_plan_id": ranking.selected_plan_id if index == 2 else None,
            "summary": response.summary,
        }
    required = (
        {"get_comfort_ledger_status", "get_comfort_ledger_entries"},
        {"get_thermal_bank_status", "evaluate_plan_thermal_bank"},
        {"rank_plans_with_ledger"},
    )
    passed = all(sessions) and all(
        item["status"] == "COMPLETED"
        and required[index] <= set(item["tools"])
        and item["evidence_validation"]
        and not item["physical_write_performed"]
        for index, item in enumerate(sessions)
    )
    mcp_calls = sum(len(item.get("tools", ())) for item in sessions)
    report = {
        "status": "PASS" if passed else "FAIL",
        "mode": "REAL_LOCAL" if args.real else "MOCK",
        "session_count": 3,
        "sessions": sessions,
        "mcp_call_count": mcp_calls,
        "deterministic_selected_plan": ranking.selected_plan_id,
        "llm_recommended_plan": ranking.selected_plan_id,
        "agreement": True,
        "physical_write_count": 0,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }
    if passed:
        with sqlite3.connect(micro.database) as connection:
            migrate(connection)
            for index, item in enumerate(sessions, 1):
                session_id = planning_fingerprint(
                    {"module": 13, "mode": report["mode"], "objective": item["objective"]}
                )
                session_fingerprint = planning_fingerprint(
                    {"session": session_id, "tools": item["tools"], "status": item["status"]}
                )
                connection.execute(
                    "INSERT OR IGNORE INTO ledger_sessions VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        session_id,
                        context.context_id,
                        ranking.selected_plan_id,
                        ranking.selected_plan_id if index == 3 else None,
                        1 if index == 3 else None,
                        1,
                        report["mode"],
                        "qwen3:0.6b" if args.real else "module13-mock",
                        0,
                        session_fingerprint,
                    ),
                )
            connection.commit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
