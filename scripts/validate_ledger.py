"""Validate Module 13 configuration, persistence, MCP surface, and artifacts."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ledger.config import load_comfort_ledger_settings
from src.mcp_server.config import load_mcp_settings
from src.mcp_server.registry import build_registry
from src.microtwin.config import load_microtwin_settings
from src.thermal_bank.config import load_thermal_bank_settings

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ledger = load_comfort_ledger_settings(ROOT / "config/comfort_ledger.yaml")
    bank = load_thermal_bank_settings(ROOT / "config/thermal_bank.yaml")
    micro = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    mcp = load_mcp_settings(ROOT / "config/mcp_server.yaml")
    registry = build_registry(mcp.control_tools_enabled)
    names = {item.name for item in registry}
    required = {
        "get_comfort_ledger_status",
        "get_comfort_ledger_entries",
        "evaluate_plan_comfort_ledger",
        "compare_comfort_ledger_evaluations",
        "get_thermal_bank_status",
        "get_thermal_bank_transactions",
        "evaluate_plan_thermal_bank",
        "rank_plans_with_ledger",
        "get_ledger_ranking",
        "select_ledger_advisory_plan",
    }
    with sqlite3.connect(micro.database) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        tables = {
            name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            for name in (
                "comfort_ledger_accounts",
                "comfort_ledger_entries",
                "comfort_debt_records",
                "comfort_debt_repayments",
                "comfort_fairness_assessments",
                "thermal_bank_accounts",
                "thermal_bank_transactions",
                "ledger_plan_evaluations",
                "ledger_rankings",
                "ledger_sessions",
            )
        }
    replay = json.loads((ROOT / "outputs/module13/final_replay.json").read_text())
    checks = {
        "ledger_config": ledger.schema_version == 1 and ledger.advisory_only,
        "bank_config": bank.schema_version == 1 and bank.advisory_only and bank.unit == "RTFU",
        "schema_8": version == 8,
        "integrity": integrity == "ok",
        "foreign_keys": not foreign_keys,
        "catalogue_v5_44": mcp.catalogue_version == 5 and len(registry) == 44,
        "ten_tools": required <= names,
        "control_disabled": not next(
            item for item in registry if item.name == "propose_guarded_control"
        ).enabled,
        "no_mutation_tools": not any(
            "forgive" in name or "mutate_balance" in name for name in names
        ),
        "replay": replay["status"] == "PASS" and replay["coverage_gap_count"] == 0,
        "persisted_evaluations": tables["ledger_plan_evaluations"] == 5,
    }
    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "database_counts": tables,
        "mcp_tool_count": len(registry),
    }
    output = ROOT / "outputs/module13/ledger_validation.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
