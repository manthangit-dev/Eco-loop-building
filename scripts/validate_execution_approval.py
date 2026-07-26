"""Validate a local execution approval against current trusted artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.execution.approval import validate_approval
from src.execution.config import load_execution_settings
from src.execution.models import ExecutionApproval
from src.execution.preflight import resolve_execution_binding

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("approval", type=Path)
    args = parser.parse_args()
    approval = ExecutionApproval.model_validate_json(args.approval.read_text(encoding="utf-8"))
    settings = load_execution_settings(ROOT / "config/execution_orchestrator.yaml")
    binding = resolve_execution_binding(settings, approval.selected_plan_id)
    validate_approval(approval, binding, settings, approval.execution_mode)
    print(
        json.dumps(
            {
                "status": "PASS",
                "approval_id": approval.approval_id,
                "fingerprint": approval.approval_fingerprint,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
