import subprocess
import sys
from pathlib import Path


def test_api_runner_script_help_imports_repository_packages() -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "-B", str(root / "scripts/run_api_baseline.py"), "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_comparison_script_help_imports_repository_packages() -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "-B", str(root / "scripts/compare_runner_outputs.py"), "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
