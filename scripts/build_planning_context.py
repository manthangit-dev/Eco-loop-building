"""Build and persist the canonical Module 11 planning context."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.planning_common import build

if __name__ == "__main__":
    context, _ = build()
    print(json.dumps(context.model_dump(mode="json"), indent=2))
