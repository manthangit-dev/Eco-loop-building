"""Real subprocess coverage for stable Module 10A user commands."""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv/Scripts/python.exe"


def run(*arguments: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(PYTHON), *arguments], cwd=cwd, text=True, capture_output=True, timeout=60
    )


@pytest.mark.parametrize(
    "arguments",
    [
        ("scripts/list_mcp_tools.py",),
        ("scripts/list_mcp_tools.py", "--json"),
        ("scripts/list_mcp_tools.py", "--enabled-only"),
        ("scripts/list_mcp_tools.py", "--classification", "CONTROL_CAPABLE"),
    ],
)
def test_tool_listing_real_subprocess(arguments: tuple[str, ...]) -> None:
    result = run(*arguments)
    assert result.returncode == 0, result.stderr
    assert "b97af3b310e48b0014f9a00a34e83737d6798b7fcda58da957b98a985477dcd6" in result.stdout


def test_tool_listing_reports_disabled_control() -> None:
    result = run("scripts/list_mcp_tools.py", "--json")
    payload = json.loads(result.stdout)
    control = next(item for item in payload["tools"] if item["name"] == "propose_guarded_control")
    assert payload["total_registered"] == 44 and control["enabled"] is False


def test_run_selection_from_other_working_directory(tmp_path: Path) -> None:
    result = run(str(ROOT / "scripts/select_demo_run.py"), cwd=tmp_path)
    payload = json.loads(result.stdout)
    assert result.returncode == 0 and payload["run_id"] == "module8-live-control"
    assert payload["latest_state_id"] == 35040 and payload["space3_available"]


def test_request_generation_uses_selected_records() -> None:
    output = ROOT / "outputs/demo/test-generated-requests"
    result = run("scripts/prepare_demo_requests.py", "--output-directory", str(output))
    manifest = json.loads(result.stdout)
    state = json.loads((output / "get_building_state.json").read_text())
    assert result.returncode == 0 and manifest["request_count"] == 9
    assert state["run_id"] == "module8-live-control" and state["state_id"] == 35040


def test_real_stdio_call_and_invalid_tool() -> None:
    valid = run(
        "scripts/call_mcp_tool.py", "--tool", "get_safety_guard_status", "--input-json", "{}"
    )
    assert valid.returncode == 0 and json.loads(valid.stdout)["success"] is True
    invalid = run("scripts/call_mcp_tool.py", "--tool", "unknown", "--input-json", "{}")
    assert invalid.returncode != 0 and json.loads(invalid.stdout)["success"] is False


def test_mock_supervisor_and_control_demos() -> None:
    prepared = ROOT / "outputs/demo/requests/describe_current_state.json"
    supervisor = run(
        "scripts/run_llm_supervisor.py", "--provider", "mock", "--input-file", str(prepared)
    )
    payload = json.loads(supervisor.stdout)
    assert supervisor.returncode == 0 and payload["physical_write_performed"] is False
    for case in ("valid", "plenum"):
        result = run("scripts/run_demo_control_proposal.py", "--case", case, "--json")
        proposal = json.loads(result.stdout)
        assert result.returncode == 0 and proposal["module_8_reached"]
        assert proposal["physical_write_performed"] is False


def test_audit_clis_are_bounded_json() -> None:
    for script in ("inspect_mcp_audit.py", "inspect_llm_sessions.py"):
        result = run(f"scripts/{script}", "--latest", "--json")
        assert result.returncode == 0 and json.loads(result.stdout)["count"] <= 1
