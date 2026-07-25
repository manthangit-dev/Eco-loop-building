from pathlib import Path

from scripts.validate_baseline import Status
from scripts.validate_sensor_extraction import validate_sensor_output

ROOT = Path(__file__).resolve().parents[1]


def test_validator_fails_cleanly_for_missing_output(tmp_path: Path) -> None:
    checks, output = validate_sensor_output(ROOT / "config/sensors.yaml", tmp_path / "missing")
    assert output == tmp_path / "missing"
    assert any(check.status is Status.FAIL for check in checks)

