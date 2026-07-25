"""Read-only verification of ThermoLedger AI Module 1 prerequisites."""

from __future__ import annotations

import importlib
import os
import platform
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

REQUIRED_FILES = (
    "README.md",
    "config/project.yaml",
    "docs/PROJECT_SCOPE.md",
    "docs/MODULE_PLAN.md",
    "docs/ACCEPTANCE_CRITERIA.md",
    "docs/DECISION_LOG.md",
    "docs/RISK_REGISTER.md",
)


class Status(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    detail: str
    remediation: str = ""


def result(
    name: str, condition: bool, success: str, failure: str, remediation: str = ""
) -> CheckResult:
    """Create a required PASS/FAIL result."""
    return CheckResult(
        name, Status.PASS if condition else Status.FAIL, success if condition else failure,
        "" if condition else remediation,
    )


def check_python_version(version: tuple[int, int]) -> CheckResult:
    return result(
        "Python 3.12",
        version == (3, 12),
        "Python major/minor is 3.12.",
        f"Python major/minor is {version[0]}.{version[1]}.",
        "Activate the project .venv created with Python 3.12.",
    )


def detect_runtime(system: str | None = None, proc_version: str | None = None) -> str:
    """Classify the current runtime without assuming an installation path."""
    system = system or platform.system()
    proc_version = proc_version if proc_version is not None else platform.uname().release
    if system == "Windows":
        return "native Windows"
    if system == "Linux" and (
        "microsoft" in proc_version.lower() or "WSL_DISTRO_NAME" in os.environ
    ):
        return "WSL"
    if system == "Linux":
        return "Linux"
    return system


def energyplus_executable(home: Path, system: str | None = None) -> Path:
    return home / ("energyplus.exe" if (system or platform.system()) == "Windows" else "energyplus")


def version_is_supported(text: str) -> bool:
    return "26.1" in text


def check_energyplus_home(value: str | None) -> tuple[Path | None, CheckResult]:
    if not value:
        return None, CheckResult(
            "ENERGYPLUS_HOME",
            Status.FAIL,
            "ENERGYPLUS_HOME is not set.",
            "Set ENERGYPLUS_HOME in .env to the EnergyPlus 26.1.0 installation directory.",
        )
    home = Path(value).expanduser()
    return home, result(
        "ENERGYPLUS_HOME",
        home.is_dir(),
        f"Directory exists: {home}",
        f"Directory does not exist: {home}",
        "Correct ENERGYPLUS_HOME in .env; do not point it at an executable.",
    )


def check_executable(home: Path, system: str | None = None) -> tuple[Path, CheckResult]:
    executable = energyplus_executable(home, system)
    return executable, result(
        "EnergyPlus executable",
        executable.is_file(),
        f"Executable exists: {executable}",
        f"Executable is missing: {executable}",
        "Install EnergyPlus 26.1.0 separately or correct ENERGYPLUS_HOME.",
    )


def run_version(executable: Path) -> tuple[str, CheckResult]:
    try:
        completed = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return "", CheckResult(
            "EnergyPlus --version", Status.FAIL, f"Could not run executable: {exc}",
            "Check executable permissions and installation integrity.",
        )
    text = f"{completed.stdout}\n{completed.stderr}".strip()
    ok = completed.returncode == 0
    return text, result(
        "EnergyPlus --version",
        ok,
        f"Command succeeded: {text}",
        f"Command exited {completed.returncode}: {text}",
        "Run the executable manually and repair the EnergyPlus installation.",
    )


def check_example_model(home: Path) -> CheckResult:
    model = home / "ExampleFiles" / "5ZoneAirCooled.idf"
    return result(
        "Example model",
        model.is_file(),
        f"Found {model}",
        f"Missing {model}",
        "Use a complete EnergyPlus 26.1.0 installation containing ExampleFiles.",
    )


def check_required_files(root: Path, required: Sequence[str] = REQUIRED_FILES) -> CheckResult:
    missing = [name for name in required if not (root / name).is_file()]
    return result(
        "Repository planning files",
        not missing,
        f"All {len(required)} required planning files exist.",
        f"Missing: {', '.join(missing)}",
        "Restore the missing repository planning files.",
    )


def exit_code(results: Sequence[CheckResult]) -> int:
    return 1 if any(item.status is Status.FAIL for item in results) else 0


def load_local_env(root: Path) -> CheckResult:
    env_file = root / ".env"
    if not env_file.exists():
        return CheckResult(
            ".env", Status.WARN, "No local .env file; .env.example documents expected values.",
            "Copy .env.example to .env and configure local paths.",
        )
    try:
        from dotenv import load_dotenv
    except ImportError:
        return CheckResult(
            ".env", Status.FAIL, "python-dotenv is not installed.",
            "Install requirements-dev.txt inside the project virtual environment.",
        )
    load_dotenv(env_file, override=False)
    return CheckResult(".env", Status.PASS, "Loaded local .env without displaying its values.")


def environment_checks(root: Path, environ: Mapping[str, str] | None = None) -> list[CheckResult]:
    """Run checks. EnergyPlus is invoked only with the non-simulation --version flag."""
    env = environ if environ is not None else os.environ
    results = [
        check_python_version((sys.version_info.major, sys.version_info.minor)),
        CheckResult(
            "Platform",
            Status.PASS,
            f"{detect_runtime()}; {platform.system()} {platform.machine()}.",
        ),
        result(
            "Git",
            bool(shutil_which("git")),
            "Git is available.",
            "Git is not available on PATH.",
            "Install Git and reopen the terminal.",
        ),
        result(
            "Virtual environment",
            bool(env.get("VIRTUAL_ENV")) or sys.prefix != sys.base_prefix,
            "A virtual environment appears active.",
            "No active project virtual environment was detected.",
            "Activate .venv before installing dependencies or running checks.",
        ),
        load_local_env(root),
        check_required_files(root),
    ]
    output = root / "data" / "output"
    writable = output.is_dir() and os.access(output, os.W_OK)
    results.append(
        result(
            "Project output directory",
            writable,
            f"Writable: {output}",
            f"Not writable or missing: {output}",
            "Create data/output and grant the current user write permission.",
        )
    )
    home, home_result = check_energyplus_home(os.environ.get("ENERGYPLUS_HOME"))
    results.append(home_result)
    if home is None or not home.is_dir():
        return results

    executable, executable_result = check_executable(home)
    results.append(executable_result)
    if executable.is_file():
        version_text, command_result = run_version(executable)
        results.append(command_result)
        if command_result.status is Status.PASS:
            results.append(
                result(
                    "EnergyPlus version",
                    version_is_supported(version_text),
                    "Reported version contains 26.1.",
                    f"Reported version is not 26.1: {version_text}",
                    "Configure ENERGYPLUS_HOME for EnergyPlus 26.1.0.",
                )
            )

    api_dir = home / "pyenergyplus"
    results.append(
        result(
            "pyenergyplus directory",
            api_dir.is_dir(),
            f"Found {api_dir}",
            f"Missing {api_dir}",
            "Use a complete EnergyPlus installation with its Python API.",
        )
    )
    if str(home) not in sys.path:
        sys.path.insert(0, str(home))
    try:
        api_module = importlib.import_module("pyenergyplus.api")
        api = api_module.EnergyPlusAPI()
        api_version = api.api_version()
        results.append(
            CheckResult("pyenergyplus import", Status.PASS, f"API version: {api_version}")
        )
    except (ImportError, AttributeError, OSError, TypeError) as exc:
        results.append(
            CheckResult(
                "pyenergyplus import", Status.FAIL, f"Import/API version failed: {exc}",
                "Verify ENERGYPLUS_HOME and use its bundled pyenergyplus package.",
            )
        )
    results.append(check_example_model(home))
    weather = home / "WeatherData"
    results.append(
        CheckResult(
            "WeatherData",
            Status.PASS if weather.is_dir() else Status.WARN,
            f"Found {weather}" if weather.is_dir() else f"Optional directory missing: {weather}",
            "Install or configure weather data before Module 2.",
        )
    )
    return results


def shutil_which(command: str) -> str | None:
    """Small wrapper that remains easy to mock in tests."""
    from shutil import which

    return which(command)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    checks = environment_checks(root)
    for item in checks:
        print(f"[{item.status.value}] {item.name}: {item.detail}")
        if item.remediation and item.status is not Status.PASS:
            print(f"       Remediation: {item.remediation}")
    counts = {status: sum(item.status is status for item in checks) for status in Status}
    print(
        f"\nSummary: {counts[Status.PASS]} passed, {counts[Status.WARN]} warned, "
        f"{counts[Status.FAIL]} failed."
    )
    print("Module 1 requires no Ollama model. No building simulation was executed.")
    return exit_code(checks)


if __name__ == "__main__":
    raise SystemExit(main())
