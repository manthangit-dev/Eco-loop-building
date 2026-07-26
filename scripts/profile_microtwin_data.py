"""Print the cached, measured MicroTwin telemetry profile."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
print((ROOT / "outputs/module12/microtwin_data_profile.json").read_text())
