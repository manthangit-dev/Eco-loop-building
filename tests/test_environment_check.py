from pathlib import Path

from scripts.check_environment import (
    CheckResult,
    Status,
    check_energyplus_home,
    check_example_model,
    check_executable,
    check_python_version,
    check_required_files,
    detect_runtime,
    energyplus_executable,
    exit_code,
    version_is_supported,
)


def test_correct_python_version() -> None:
    assert check_python_version((3, 12)).status is Status.PASS


def test_incorrect_python_version() -> None:
    assert check_python_version((3, 11)).status is Status.FAIL


def test_windows_executable_path(tmp_path: Path) -> None:
    assert energyplus_executable(tmp_path, "Windows") == tmp_path / "energyplus.exe"


def test_linux_executable_path(tmp_path: Path) -> None:
    assert energyplus_executable(tmp_path, "Linux") == tmp_path / "energyplus"


def test_missing_energyplus_home() -> None:
    home, check = check_energyplus_home(None)
    assert home is None
    assert check.status is Status.FAIL


def test_missing_executable(tmp_path: Path) -> None:
    _, check = check_executable(tmp_path, "Linux")
    assert check.status is Status.FAIL


def test_valid_version_text() -> None:
    assert version_is_supported("EnergyPlus, Version 26.1.0")


def test_invalid_version_text() -> None:
    assert not version_is_supported("EnergyPlus, Version 25.2.0")


def test_missing_example_model(tmp_path: Path) -> None:
    assert check_example_model(tmp_path).status is Status.FAIL


def test_wsl_detection() -> None:
    assert detect_runtime("Linux", "5.15.0-microsoft-standard-WSL2") == "WSL"


def test_required_file_verification(tmp_path: Path) -> None:
    (tmp_path / "one.md").write_text("ok", encoding="utf-8")
    assert check_required_files(tmp_path, ("one.md",)).status is Status.PASS
    assert check_required_files(tmp_path, ("missing.md",)).status is Status.FAIL


def test_summary_exit_code() -> None:
    assert exit_code([CheckResult("ok", Status.PASS, "ok")]) == 0
    assert exit_code([CheckResult("bad", Status.FAIL, "bad")]) == 1
