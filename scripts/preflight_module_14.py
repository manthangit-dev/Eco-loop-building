"""Create the Module 13-to-14 immutable execution preflight report."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.execution.config import load_execution_settings
from src.execution.preflight import resolve_execution_binding

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/module14/module13_execution_preflight.json"
    )
    args = parser.parse_args()
    started = time.monotonic()
    binding = resolve_execution_binding(
        load_execution_settings(ROOT / "config/execution_orchestrator.yaml")
    )
    report = {
        "status": "PASS",
        **binding,
        "physical_write_count": 0,
        "energyplus_process_count": 0,
        "runtime_seconds": round(time.monotonic() - started, 3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
