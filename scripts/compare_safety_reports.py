"""Compare deterministic Module 8 report fingerprints."""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    args = parser.parse_args()
    first, second = json.loads(args.first.read_text()), json.loads(args.second.read_text())
    passed = first["fingerprint"] == second["fingerprint"]
    print(
        json.dumps(
            {
                "status": "PASS" if passed else "FAIL",
                "first": first["fingerprint"],
                "second": second["fingerprint"],
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
