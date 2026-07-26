"""Evaluate all persisted candidates and print only Thermal Bank summaries."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
output = ROOT / "outputs/ledger/evaluations.json"
result = subprocess.run(
    [sys.executable, str(ROOT / "scripts/evaluate_comfort_ledger.py"), "--output", str(output)],
    check=False,
)
if result.returncode:
    raise SystemExit(result.returncode)
payload = json.loads(output.read_text())
print(
    json.dumps(
        [{"plan_id": item["plan_id"], **item["bank"]} for item in payload["evaluations"]], indent=2
    )
)
