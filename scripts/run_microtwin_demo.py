"""Run the cached deterministic Module 12 demonstration."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
result = subprocess.run(
    [sys.executable, str(ROOT / "scripts/evaluate_microtwin_candidates.py")],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=False,
)
payload = json.loads(result.stdout)
summary = {
    "status": payload["status"],
    "rollout_count": payload["rollout_count"],
    "selected_plan": payload["selected_plan"],
    "rankings_agree": payload["rankings_agree"],
    "physical_write_count": payload["physical_write_count"],
    "energyplus_processes_started": payload["energyplus_processes_started"],
}
print(json.dumps(summary, indent=2))
raise SystemExit(0 if result.returncode == 0 and summary["status"] == "PASS" else 1)
