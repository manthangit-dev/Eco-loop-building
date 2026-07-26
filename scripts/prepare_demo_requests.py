"""Generate validated demo requests from the dynamically selected recorded run."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent.models import ObjectiveType, SupervisorRequest  # noqa: E402
from src.mcp_server.models import ControlProposalInput  # noqa: E402

from scripts.demo_common import select_demo_run  # noqa: E402


def proposal(selected: dict[str, Any], *, plenum: bool) -> dict[str, object]:
    zone = "PLENUM-1" if plenum else "SPACE3-1"
    return ControlProposalInput(
        run_id=str(selected["run_id"]),
        environment_id=str(selected["environment_id"]),
        source_state_sequence=int(selected["latest_state_id"]),
        current_sequence=int(selected["latest_state_id"]) + 1,
        component_type="Zone Temperature Control",
        control_type="Cooling Setpoint",
        actuator_key=zone,
        zone=zone,
        units="C",
        requested_value=24.0,
        client_request_id=f"demo-{'plenum' if plenum else 'valid'}",
    ).model_dump(mode="json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, default=ROOT / "outputs/demo/requests")
    args = parser.parse_args()
    try:
        selected = select_demo_run()
        run = {"run_id": selected["run_id"]}
        requests: dict[str, object] = {
            "list_available_runs": {"limit": 10},
            "get_run_metadata": run,
            "get_building_state": {**run, "state_id": selected["latest_state_id"]},
            "get_zone_state": {**run, "state_id": selected["latest_state_id"], "zone": "SPACE3-1"},
            "get_safety_guard_status": {},
            "get_physical_write_audit": {**run, "limit": 5},
            "valid_control_proposal": proposal(selected, plenum=False),
            "plenum_control_proposal": proposal(selected, plenum=True),
        }
        supervisor = SupervisorRequest(
            request_id="demo-describe-current-state",
            objective_type=ObjectiveType.DESCRIBE_CURRENT_STATE,
            objective_text="Describe the selected latest recorded building state.",
            run_id=str(selected["run_id"]),
            state_id=int(selected["latest_state_id"]),
            dry_run_only=True,
        ).model_dump(mode="json")
        output = args.output_directory.resolve()
        output.mkdir(parents=True, exist_ok=True)
        for name, payload in {**requests, "describe_current_state": supervisor}.items():
            (output / f"{name}.json").write_text(
                json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8"
            )
        manifest = {
            "success": True,
            "selected": selected,
            "request_count": len(requests) + 1,
            "request_schema_version": 1,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "output_directory": str(output.relative_to(ROOT)),
        }
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(json.dumps(manifest, indent=2))
        return 0
    except Exception as exc:
        print(f"Demo request generation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
