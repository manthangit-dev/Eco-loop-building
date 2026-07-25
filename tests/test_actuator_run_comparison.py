from pathlib import Path

from scripts.compare_actuator_runs import compare

ROOT = Path(__file__).resolve().parents[1]


def test_real_persisted_control_and_intervention_compare() -> None:
    passed, output = compare(ROOT / "config/actuators.yaml")
    assert passed
    assert output.is_file()
