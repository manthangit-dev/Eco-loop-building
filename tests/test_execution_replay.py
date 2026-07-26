from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_all_execution_replay_fixtures_are_dedicated() -> None:
    manifest = json.loads(
        (ROOT / "tests/fixtures/execution/module14_replay_manifest.json").read_text()
    )
    rows = manifest["scenarios"]
    assert len(rows) == 130
    assert len({row["fixture_key"] for row in rows}) == 130
    assert all(row["fixture_type"] == "DEDICATED_EXECUTABLE_FIXTURE" for row in rows)
    assert all(row["concrete_mutation"] for row in rows)
