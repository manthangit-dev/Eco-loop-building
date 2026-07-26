"""Print the deterministic cached MicroTwin ranking."""

import json
from pathlib import Path

payload = json.loads(
    (
        Path(__file__).resolve().parents[1] / "outputs/microtwin/candidate_evaluation.json"
    ).read_text()
)
print(
    json.dumps(
        {"ranking": payload["microtwin_ranking"], "selected_plan": payload["selected_plan"]},
        indent=2,
    )
)
