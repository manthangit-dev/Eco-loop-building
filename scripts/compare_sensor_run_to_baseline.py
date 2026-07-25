"""Compare Module 4 sensor run physical outputs with the verified Module 3 run."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

import yaml  # type: ignore[import-untyped]

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.compare_runner_outputs import (  # noqa: E402
    compare_outputs,
    comparison_exit_code,
)


def compare_sensor_run(
    api_config: Path, sensor_output: Path | None = None
) -> tuple[int, Path]:
    root = api_config.resolve().parents[1]
    config = yaml.safe_load(api_config.read_text(encoding="utf-8"))
    manifest = json.loads((root / "models/MODEL_MANIFEST.json").read_text(encoding="utf-8"))
    module_3 = root / config["paths"]["module_3_output"]
    module_4 = sensor_output or root / "data/output/module_4_sensor_extraction/current"
    comparisons = compare_outputs(
        module_3,
        module_4,
        str(config["runner"]["output_prefix"]),
        str(manifest["derived_baseline_sha256"]),
        str(manifest["weather_sha256"]),
    )
    summary = {
        "status": "PASS" if comparison_exit_code(comparisons) == 0 else "FAIL",
        "comparison_basis": "physical and structural parity; no savings calculation",
        "comparisons": [asdict(item) for item in comparisons],
    }
    path = module_4 / "sensor_baseline_comparison.json"
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return comparison_exit_code(comparisons), path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-config", type=Path, default=Path("config/api_runner.yaml"))
    parser.add_argument("--sensor-output", type=Path)
    args = parser.parse_args(argv)
    code, path = compare_sensor_run(args.api_config, args.sensor_output)
    print(f"Sensor comparison: {'PASS' if code == 0 else 'FAIL'}")
    print(f"Comparison summary: {path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
