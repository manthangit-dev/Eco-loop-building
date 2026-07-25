from pathlib import Path

from scripts.validate_actuator_test import validate
from scripts.validate_baseline import Status

ROOT = Path(__file__).resolve().parents[1]


def test_real_persisted_experiment_validation_is_complete() -> None:
    checks, output = validate(ROOT / "config/actuators.yaml")
    assert output.is_file()
    assert not [item for item in checks if item.status is Status.FAIL]
