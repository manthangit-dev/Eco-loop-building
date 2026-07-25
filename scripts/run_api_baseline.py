"""Run the verified baseline through the EnergyPlus Python Runtime API."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.energyplus.run_result import RunStatus  # noqa: E402
from src.energyplus.runner import EnergyPlusRunner  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/api_runner.yaml"))
    parser.add_argument("--no-clean", action="store_true")
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--skip-comparison", action="store_true")
    args = parser.parse_args(argv)
    result = EnergyPlusRunner(args.config).run(
        no_clean=args.no_clean,
        timeout_override=args.timeout,
        quiet=args.quiet,
        skip_validation=args.skip_validation,
        skip_comparison=args.skip_comparison,
    )
    print(f"Run ID: {result.run_id}")
    print(f"EnergyPlus: {result.energyplus_version}")
    print(f"API version: {result.api_version}")
    print(f"Model: {result.model_path}")
    print(f"Weather: {result.weather_path}")
    print(f"Output: {result.output_directory}")
    if result.progress_events:
        print(f"Final progress: {result.progress_events[-1]['progress']}%")
    print(f"EnergyPlus exit code: {result.exit_code}")
    print(
        "Callbacks: "
        f"progress={len(result.progress_events)}, messages={result.message_count}, "
        f"environments={result.environment_start_count}, "
        f"warmups={result.warmup_complete_count}, errors={len(result.callback_errors)}"
    )
    print(f"Validation: {result.validation_status}")
    print(f"Comparison: {result.comparison_status}")
    print(f"Elapsed: {result.elapsed_seconds:.2f} seconds")
    print(result.status.value)
    if result.error_message:
        print(f"Error: {result.error_message}")
    return 0 if result.status is RunStatus.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
