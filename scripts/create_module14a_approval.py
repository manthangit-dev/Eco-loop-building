"""Create the exact-window local simulation approval for Module 14A."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.execution.exact_approval import create_exact_approval, validate_exact_approval
from src.storage.execution_store import ExecutionStore

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true", required=True)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/module14a/exact_approval.json"
    )
    args = parser.parse_args()
    package = json.loads((ROOT / "outputs/module14a/context_selection_report.json").read_text())
    runtime = json.loads((ROOT / "outputs/module14a/runtime_manifest.json").read_text())
    approval = create_exact_approval(package, runtime, str(ROOT.resolve()))
    validate_exact_approval(approval, package, runtime)
    args.output.write_text(
        approval.model_dump_json(indent=2, exclude_computed_fields=True) + "\n",
        encoding="utf-8",
    )
    with sqlite3.connect(ROOT / "data/output/module_12_microtwin/microtwin.db") as connection:
        ExecutionStore(connection).persist_approval(approval)
    print(
        json.dumps(
            {
                "status": "PASS",
                "approval_id": approval.approval_id,
                "approval_fingerprint": approval.approval_fingerprint,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
