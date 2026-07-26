"""Print a persisted candidate rollout selected by plan ID."""

import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("plan_id")
args = parser.parse_args()
payload = json.loads(
    (
        Path(__file__).resolve().parents[1] / "outputs/microtwin/candidate_evaluation.json"
    ).read_text()
)
match = next((item for item in payload["rollouts"] if item["plan_id"] == args.plan_id), None)
if match is None:
    raise SystemExit("unknown or ineligible plan_id")
print(json.dumps(match, indent=2))
