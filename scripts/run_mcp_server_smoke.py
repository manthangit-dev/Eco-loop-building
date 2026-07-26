"""Run the real local stdio MCP server smoke test with a concise report."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.smoke_mcp_server import smoke  # noqa: E402


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        report = asyncio.run(smoke())
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "PASS" else 3
    except Exception as exc:
        print(f"MCP server smoke failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
