import json
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from scripts.validate_baseline import (
    Check,
    Status,
    check_checksum,
    check_file,
    is_safe_output_directory,
    load_manifest,
    load_yaml,
    parse_error_summary,
    sha256_file,
    validate_run,
    validation_exit_code,
)


def _write(path: Path, text: str = "data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _project(tmp_path: Path, error_text: str | None = None) -> tuple[Path, Path]:
    source = _write(tmp_path / "models/source/model.idf", "source")
    baseline = _write(tmp_path / "models/baseline/model.idf", "baseline")
    weather = _write(tmp_path / "weather/input/weather.epw", "weather")
    output = tmp_path / "data/output/module_2_baseline/current"
    output.mkdir(parents=True)
    prefix = "test"
    if error_text is not None:
        _write(output / f"{prefix}.err", error_text)
    for extension in ("eio", "csv", "htm", "sql"):
        _write(output / f"{prefix}.{extension}")
    _write(
        output / "run_metadata.json",
        json.dumps(
            {
                "energyplus_exit_code": 0,
                "installation_generated_files_before": [],
                "installation_generated_files_after": [],
            }
        ),
    )
    manifest: dict[str, Any] = {
        "repository_source_copy_sha256": sha256_file(source),
        "derived_baseline_sha256": sha256_file(baseline),
        "weather_filename": weather.name,
        "weather_sha256": sha256_file(weather),
    }
    _write(tmp_path / "models/MODEL_MANIFEST.json", json.dumps(manifest))
    config: dict[str, Any] = {
        "baseline": {
            "source_model": "models/source/model.idf",
            "baseline_model": "models/baseline/model.idf",
            "weather_filename": weather.name,
            "output_directory": "data/output/module_2_baseline/current",
            "output_prefix": prefix,
        },
        "validation": {
            "required_output_files": [
                "test.err",
                "test.eio",
                "test.csv",
                "test.htm",
                "test.sql",
            ],
            "optional_dictionary_files": [],
            "minimum_non_empty_output_files": 5,
        },
    }
    config_path = tmp_path / "config/baseline.yaml"
    _write(config_path, yaml.safe_dump(config))
    return config_path, output


def test_missing_output_directory(tmp_path: Path) -> None:
    config, output = _project(tmp_path)
    for child in output.iterdir():
        child.unlink()
    output.rmdir()
    checks, _ = validate_run(config)
    assert any(check.name == "Output directory" and check.status is Status.FAIL for check in checks)


def test_missing_error_file(tmp_path: Path) -> None:
    assert check_file(tmp_path / "missing.err", "Error report").status is Status.FAIL


def test_empty_error_file(tmp_path: Path) -> None:
    assert check_file(_write(tmp_path / "empty.err", ""), "Error report").status is Status.FAIL


def test_successful_error_summary() -> None:
    counts = parse_error_summary("EnergyPlus Completed Successfully-- 0 Warning; 0 Severe Errors;")
    assert counts.warnings == counts.severe == counts.fatal == 0


def test_warning_only_error_summary() -> None:
    counts = parse_error_summary("EnergyPlus Completed Successfully-- 3 Warnings; 0 Severe Errors;")
    assert counts.warnings == 3
    assert counts.severe == counts.fatal == 0


def test_severe_error_summary() -> None:
    counts = parse_error_summary("EnergyPlus Terminated-- 2 Warnings; 1 Severe Errors;")
    assert counts.severe == 1


def test_fatal_error_summary() -> None:
    counts = parse_error_summary("**  Fatal  ** Bad input\n0 Warning; 1 Severe Errors;")
    assert counts.fatal == 1


def test_final_summary_wins_over_detailed_lines() -> None:
    text = (
        "** Warning ** one\n** Severe ** one\n"
        "EnergyPlus Completed-- 4 Warnings; 2 Severe Errors;"
    )
    counts = parse_error_summary(text)
    assert counts.warnings == 4
    assert counts.severe == 2
    assert counts.used_final_summary


def test_missing_required_output_file(tmp_path: Path) -> None:
    assert check_file(tmp_path / "result.csv", "CSV").status is Status.FAIL


def test_empty_required_output_file(tmp_path: Path) -> None:
    assert check_file(_write(tmp_path / "result.csv", ""), "CSV").status is Status.FAIL


def test_valid_checksum(tmp_path: Path) -> None:
    path = _write(tmp_path / "input", "stable")
    assert check_checksum(path, sha256_file(path), "checksum").status is Status.PASS


def test_invalid_checksum(tmp_path: Path) -> None:
    path = _write(tmp_path / "input", "changed")
    assert check_checksum(path, "0" * 64, "checksum").status is Status.FAIL


def test_source_model_mutation_detection(tmp_path: Path) -> None:
    config, _ = _project(tmp_path, "0 Warning; 0 Severe Errors;")
    _write(tmp_path / "models/source/model.idf", "mutated")
    checks, _ = validate_run(config)
    assert any(check.name == "Source checksum" and check.status is Status.FAIL for check in checks)


def test_weather_mutation_detection(tmp_path: Path) -> None:
    config, _ = _project(tmp_path, "0 Warning; 0 Severe Errors;")
    _write(tmp_path / "weather/input/weather.epw", "mutated")
    checks, _ = validate_run(config)
    assert any(check.name == "Weather checksum" and check.status is Status.FAIL for check in checks)


def test_output_directory_safety(tmp_path: Path) -> None:
    allowed = tmp_path / "data/output/module_2_baseline"
    assert is_safe_output_directory(allowed / "current", allowed)
    assert not is_safe_output_directory(tmp_path / "models", allowed)
    assert not is_safe_output_directory(allowed, allowed)


def test_validation_exit_code() -> None:
    assert validation_exit_code([Check("pass", Status.PASS, "ok")]) == 0
    assert validation_exit_code([Check("fail", Status.FAIL, "bad")]) == 1


def test_manifest_loading(tmp_path: Path) -> None:
    path = _write(tmp_path / "manifest.json", '{"energyplus_version": "26.1.0"}')
    assert load_manifest(path)["energyplus_version"] == "26.1.0"


def test_validation_accepts_utf8_bom_metadata(tmp_path: Path) -> None:
    config, output = _project(
        tmp_path, "EnergyPlus Completed Successfully-- 0 Warning; 0 Severe Errors;"
    )
    metadata = (output / "run_metadata.json").read_text(encoding="utf-8")
    (output / "run_metadata.json").write_text(metadata, encoding="utf-8-sig")
    checks, _ = validate_run(config)
    assert not any(
        check.name == "Process metadata" and check.status is Status.FAIL for check in checks
    )


def test_yaml_configuration_loading(tmp_path: Path) -> None:
    path = _write(tmp_path / "baseline.yaml", "baseline:\n  name: test\n")
    assert load_yaml(path)["baseline"]["name"] == "test"


def test_complete_synthetic_validation(tmp_path: Path) -> None:
    config, output = _project(
        tmp_path, "EnergyPlus Completed Successfully-- 1 Warning; 0 Severe Errors;"
    )
    checks, _ = validate_run(config)
    assert validation_exit_code(checks) == 0
    assert (output / "validation_summary.json").is_file()
