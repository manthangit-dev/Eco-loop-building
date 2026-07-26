"""Evaluate and print the deterministic Module 13 ranking."""

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
print(json.dumps(json.loads(output.read_text())["ranking"], indent=2))
