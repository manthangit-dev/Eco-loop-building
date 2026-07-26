"""Generate and persist deterministic advisory candidate plans."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.planning.generator import select_deterministic

from scripts.planning_common import build

if __name__ == "__main__":
    context, plans = build()
    print(
        json.dumps(
            {
                "status": "PASS",
                "context_id": context.context_id,
                "candidate_count": len(plans),
                "eligible_count": sum(p.eligible for p in plans),
                "selected_plan": select_deterministic(plans).plan_id,
                "plans": [p.model_dump(mode="json") for p in plans],
                "physical_write_count": 0,
            },
            indent=2,
        )
    )
