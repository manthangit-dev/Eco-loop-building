"""Revalidate persisted mock and real Module 13 sessions without invoking a model."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
reports = [
    json.loads((ROOT / f"outputs/module13/{name}_model_smoke.json").read_text())
    for name in ("mock", "real")
]
passed = all(
    item["status"] == "PASS"
    and item["session_count"] == 3
    and item["physical_write_count"] == 0
    and all(
        session["status"] == "COMPLETED"
        and session["evidence_validation"]
        and not session["physical_write_performed"]
        for session in item["sessions"]
    )
    for item in reports
)
print(
    json.dumps(
        {
            "status": "PASS" if passed else "FAIL",
            "mock_sessions": 3,
            "real_sessions": 3,
            "real_mcp_calls": reports[1]["mcp_call_count"],
        },
        indent=2,
    )
)
raise SystemExit(0 if passed else 1)
