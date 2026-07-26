"""Run annual EnergyPlus with controller proposals guarded in no-write shadow mode."""

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.fallback_live_common import run_live_mode

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    passed, _ = run_live_mode(
        root / "config/api_runner.yaml",
        root / "config/sensors.yaml",
        root / "config/state_bus.yaml",
        root / "config/fallback_controller.yaml",
        "live_shadow",
        safety_config=root / "config/safety_guard.yaml",
        output_override=root / "data/output/module_8_safety_guard/live_shadow/current",
    )
    raise SystemExit(0 if passed else 1)
