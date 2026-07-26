"""Run the full annual one-zone Module 7 live fallback controller."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.fallback_live_common import run_live_mode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-config", type=Path, default=Path("config/api_runner.yaml"))
    parser.add_argument("--sensor-config", type=Path, default=Path("config/sensors.yaml"))
    parser.add_argument("--state-config", type=Path, default=Path("config/state_bus.yaml"))
    parser.add_argument(
        "--controller-config", type=Path, default=Path("config/fallback_controller.yaml")
    )
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--skip-comparison", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]

    def resolve(value: Path) -> Path:
        return value if value.is_absolute() else root / value

    passed, _ = run_live_mode(
        resolve(args.api_config),
        resolve(args.sensor_config),
        resolve(args.state_config),
        resolve(args.controller_config),
        "live_control",
        no_clean=args.no_clean,
        timeout=args.timeout,
        quiet=args.quiet,
        skip_comparison=args.skip_comparison,
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
