"""Print persisted Comfort Ledger evaluation evidence."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
print(json.dumps(json.loads((ROOT / "outputs/ledger/evaluations.json").read_text()), indent=2))
