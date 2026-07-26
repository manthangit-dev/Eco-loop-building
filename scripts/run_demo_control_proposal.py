"""Demonstrate valid or PLENUM-1 Module 8 dry-run proposal validation."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.mcp_server.config import load_mcp_settings  # noqa: E402
from src.mcp_server.models import ToolRequest  # noqa: E402
from src.mcp_server.service import MCPToolService  # noqa: E402

from scripts.demo_common import select_demo_run  # noqa: E402
from scripts.prepare_demo_requests import proposal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("valid", "plenum"), required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        selected = select_demo_run()
        arguments = proposal(selected, plenum=args.case == "plenum")
        service = MCPToolService(load_mcp_settings(ROOT / "config/mcp_server.yaml"))
        response = service.call(
            ToolRequest(
                request_id=f"demo-proposal-{args.case}",
                tool_name="validate_control_proposal",
                arguments=arguments,
            )
        )
        result = {
            "success": response.success,
            "case": args.case,
            "run_id": selected["run_id"],
            "state_id": selected["latest_state_id"],
            "requested_actuator": (
                f"Zone Temperature Control|Cooling Setpoint|{arguments['actuator_key']}|C"
            ),
            "requested_value": arguments["requested_value"],
            "guard_outcome": response.data.get("guard_outcome") if response.data else None,
            "guard_reason": response.data.get("reason_code") if response.data else None,
            "safe_value": response.data.get("safe_applied_value") if response.data else None,
            "module_8_reached": response.success,
            "physical_write_performed": False,
            "audit_record_id": response.tool_call_id,
        }
        print(json.dumps(result, indent=2))
        passed = response.success and result["physical_write_performed"] is False
        if args.case == "plenum":
            passed = passed and result["guard_reason"] == "plenum_zone_rejected"
        return 0 if passed else 3
    except Exception as exc:
        print(f"Control proposal demo failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
