"""Create an exact local operator approval artifact."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.execution.approval import create_approval
from src.execution.config import load_execution_settings
from src.execution.models import ExecutionMode
from src.execution.preflight import resolve_execution_binding
from src.storage.execution_store import ExecutionStore

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--mode", choices=[x.value for x in ExecutionMode], required=True)
    parser.add_argument("--expires-in-minutes", type=int, required=True)
    parser.add_argument("--maximum-writes", type=int, required=True)
    parser.add_argument("--maximum-resets", type=int, required=True)
    parser.add_argument("--simulation-only", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    settings = load_execution_settings(ROOT / "config/execution_orchestrator.yaml")
    binding = resolve_execution_binding(settings, args.plan_id)
    approval = create_approval(
        binding,
        settings,
        ExecutionMode(args.mode),
        args.expires_in_minutes,
        args.maximum_writes,
        args.maximum_resets,
        args.simulation_only,
        args.confirm,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        approval.model_dump_json(indent=2, exclude_computed_fields=True) + "\n",
        encoding="utf-8",
    )
    with sqlite3.connect(settings.database) as connection:
        ExecutionStore(connection).persist_approval(approval)
    result = {"status": "PASS", "approval": approval.model_dump(mode="json")}
    print(json.dumps(result, indent=2, default=str) if args.json else approval.approval_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
