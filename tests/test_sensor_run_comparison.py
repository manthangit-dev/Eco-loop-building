import json
from pathlib import Path

from scripts.compare_runner_outputs import compare_outputs, comparison_exit_code

ROOT = Path(__file__).resolve().parents[1]


def test_sensor_comparison_accepts_identical_physical_output() -> None:
    manifest = json.loads((ROOT / "models/MODEL_MANIFEST.json").read_text())
    output = ROOT / "data/output/module_3_api_runner/current"
    comparisons = compare_outputs(
        output,
        output,
        "thermoledger",
        manifest["derived_baseline_sha256"],
        manifest["weather_sha256"],
    )
    assert comparison_exit_code(comparisons) == 0
