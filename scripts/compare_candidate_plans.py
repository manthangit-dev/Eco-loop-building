"""Print deterministic candidate ranking."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.planning_common import build

if __name__ == "__main__":
    _, plans = build()
    print(
        json.dumps(
            {
                "ranking": [
                    {
                        "plan_id": p.plan_id,
                        "strategy": p.strategy_type,
                        "eligible": p.eligible,
                        "advisory_score": p.advisory_score,
                    }
                    for p in plans
                ],
                "physical_write_count": 0,
            },
            indent=2,
        )
    )
