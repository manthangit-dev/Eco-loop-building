"""List the canonical Module 9 MCP catalogue."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.mcp_server.config import load_mcp_settings  # noqa: E402
from src.mcp_server.registry import build_registry, catalogue_fingerprint  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config/mcp_server.yaml")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--enabled-only", action="store_true")
    parser.add_argument(
        "--classification", choices=("READ_ONLY", "PROPOSAL_ONLY", "CONTROL_CAPABLE")
    )
    args = parser.parse_args()
    try:
        settings = load_mcp_settings(args.config.resolve())
        complete = build_registry(settings.control_tools_enabled)
        tools = tuple(
            item
            for item in complete
            if (not args.enabled_only or item.enabled)
            and (args.classification is None or item.classification.value == args.classification)
        )
        payload = {
            "total_registered": len(complete),
            "returned": len(tools),
            "catalogue_fingerprint": catalogue_fingerprint(complete),
            "tools": [item.model_dump(mode="json") for item in tools],
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Registered MCP tools: {len(complete)}")
            print(f"Catalogue fingerprint: {payload['catalogue_fingerprint']}")
            for item in tools:
                print(
                    f"{item.name} | {item.classification.value} | enabled={item.enabled} | "
                    f"schema={item.schema_version} | {item.purpose}"
                )
        return 0
    except Exception as exc:
        print(f"MCP tool listing failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
