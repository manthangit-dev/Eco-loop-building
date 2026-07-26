"""Print persisted Thermal Bank summaries."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
payload = json.loads((ROOT / "outputs/ledger/evaluations.json").read_text())
print(
    json.dumps(
        {
            "status": payload["status"],
            "unit": "RTFU",
            "plans": [
                {"plan_id": item["plan_id"], **item["bank"]} for item in payload["evaluations"]
            ],
        },
        indent=2,
    )
)
