import json
from pathlib import Path

from scripts.compare_runner_outputs import (
    Comparison,
    compare_outputs,
    comparison_exit_code,
    csv_shape,
)


def _run(
    directory: Path,
    *,
    header: str = "Date/Time,Value",
    rows: tuple[str, ...] = ("01/01  01:00:00,1", "12/31  24:00:00,2"),
    warnings: int = 0,
    severe: int = 0,
) -> None:
    directory.mkdir(parents=True)
    (directory / "run_metadata.json").write_text(
        json.dumps(
            {
                "energyplus_version": "EnergyPlus 26.1",
                "energyplus_exit_code": 0,
                "exit_code": 0,
                "model_sha256": "model",
                "weather_sha256": "weather",
            }
        ),
        encoding="utf-8",
    )
    (directory / "thermoledger.err").write_text(
        f"EnergyPlus Completed Successfully-- {warnings} Warnings; {severe} Severe Errors;",
        encoding="utf-8",
    )
    (directory / "thermoledger.csv").write_text("\n".join((header, *rows)) + "\n", encoding="utf-8")
    for suffix in ("eio", "htm", "sql", "rdd", "mdd"):
        (directory / f"thermoledger.{suffix}").write_text("result", encoding="utf-8")


def _comparison(tmp_path: Path) -> list[Comparison]:
    left = tmp_path / "module2"
    right = tmp_path / "module3"
    _run(left)
    _run(right)
    return compare_outputs(left, right, "thermoledger", "model", "weather")


def test_matching_csv_structure(tmp_path: Path) -> None:
    assert comparison_exit_code(_comparison(tmp_path)) == 0


def test_row_count_mismatch(tmp_path: Path) -> None:
    left, right = tmp_path / "left", tmp_path / "right"
    _run(left)
    _run(right, rows=("01/01  01:00:00,1",))
    comparisons = compare_outputs(left, right, "thermoledger", "model", "weather")
    assert not next(item for item in comparisons if item.name == "CSV row count").matches


def test_header_mismatch(tmp_path: Path) -> None:
    left, right = tmp_path / "left", tmp_path / "right"
    _run(left)
    _run(right, header="Date/Time,Different")
    comparisons = compare_outputs(left, right, "thermoledger", "model", "weather")
    assert not next(item for item in comparisons if item.name == "CSV header").matches


def test_timestamp_mismatch(tmp_path: Path) -> None:
    left, right = tmp_path / "left", tmp_path / "right"
    _run(left)
    _run(right, rows=("02/01  01:00:00,1", "12/31  24:00:00,2"))
    comparisons = compare_outputs(left, right, "thermoledger", "model", "weather")
    assert not next(item for item in comparisons if item.name == "First timestamp").matches


def test_severe_mismatch(tmp_path: Path) -> None:
    left, right = tmp_path / "left", tmp_path / "right"
    _run(left)
    _run(right, severe=1)
    comparisons = compare_outputs(left, right, "thermoledger", "model", "weather")
    assert not next(item for item in comparisons if item.name == "Severe count").matches


def test_missing_sql(tmp_path: Path) -> None:
    left, right = tmp_path / "left", tmp_path / "right"
    _run(left)
    _run(right)
    (right / "thermoledger.sql").unlink()
    comparisons = compare_outputs(left, right, "thermoledger", "model", "weather")
    assert not next(item for item in comparisons if item.name == "SQL output").matches


def test_checksum_reporting(tmp_path: Path) -> None:
    path = tmp_path / "result.csv"
    path.write_text("Date/Time,Value\n01/01,1\n", encoding="utf-8")
    assert len(csv_shape(path).sha256) == 64


def test_comparison_exit_code() -> None:
    assert comparison_exit_code([Comparison("ok", True, 1, 1, "match")]) == 0
    assert comparison_exit_code([Comparison("bad", False, 1, 2, "mismatch")]) == 1
