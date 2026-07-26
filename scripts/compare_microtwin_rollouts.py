"""Print the deterministic comparison of cached candidate rollouts."""

import json
from pathlib import Path

payload = json.loads(
    (
        Path(__file__).resolve().parents[1] / "outputs/microtwin/candidate_evaluation.json"
    ).read_text()
)
print(
    json.dumps(
        {key: payload[key] for key in ("microtwin_ranking", "advisory_ranking", "rankings_agree")},
        indent=2,
    )
)
