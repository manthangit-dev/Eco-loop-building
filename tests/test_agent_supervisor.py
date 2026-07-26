from pathlib import Path

from src.agent.models import ObjectiveType, SupervisorRequest
from src.agent.supervisor import Supervisor
from src.llm.config import load_llm_settings
from src.llm.mock_provider import DeterministicMockProvider
from src.llm.models import ModelToolCall, ProviderOutput
from src.mcp_server.config import load_mcp_settings
from src.mcp_server.service import MCPToolService


def setup(tmp_path: Path, outputs: list[ProviderOutput]) -> Supervisor:
    root = Path(__file__).resolve().parents[1]
    settings = load_llm_settings(root / "config/llm_supervisor.yaml").model_copy(
        update={"database": tmp_path / "llm.db", "output_root": tmp_path}
    )
    tools = MCPToolService(load_mcp_settings(root / "config/mcp_server.yaml"), audit=False)
    return Supervisor(settings, DeterministicMockProvider(outputs), tools)


def request(identity: str = "request") -> SupervisorRequest:
    return SupervisorRequest(
        request_id=identity,
        objective_type=ObjectiveType.DESCRIBE_CURRENT_STATE,
        objective_text="Describe recorded state",
        run_id="module8-live-control",
    )


def test_one_tool_then_final_and_exact_replay(tmp_path: Path) -> None:
    outputs = [
        ProviderOutput(
            tool_call=ModelToolCall(
                name="get_run_metadata", arguments={"run_id": "module8-live-control"}
            )
        ),
        ProviderOutput(text="Recorded run is available."),
    ]
    supervisor = setup(tmp_path, outputs)
    first = supervisor.run(request())
    assert first.status == "COMPLETED" and len(first.tool_calls) == 1
    assert not first.physical_write_performed


def test_denied_control_fails_closed(tmp_path: Path) -> None:
    supervisor = setup(
        tmp_path,
        [ProviderOutput(tool_call=ModelToolCall(name="propose_guarded_control", arguments={}))],
    )
    result = supervisor.run(request("denied"))
    assert result.status == "FAILED_CLOSED" and not result.physical_write_performed


def test_repeated_call_detected(tmp_path: Path) -> None:
    call = ProviderOutput(
        tool_call=ModelToolCall(
            name="get_run_metadata", arguments={"run_id": "module8-live-control"}
        )
    )
    result = setup(tmp_path, [call, call]).run(request("repeat"))
    assert result.status == "FAILED_CLOSED" and "repeated_tool_call" in result.warnings


def test_required_microtwin_evidence_is_prefetched_after_one_correction(
    tmp_path: Path,
) -> None:
    supervisor = setup(
        tmp_path,
        [
            ProviderOutput(text="Answered without evidence."),
            ProviderOutput(text="Still no tool call."),
            ProviderOutput(text="Thermal validation is based on the supplied evidence."),
        ],
    )
    result = supervisor.run(
        SupervisorRequest(
            request_id="required-prefetch",
            objective_type=ObjectiveType.EXPLAIN_MICROTWIN_VALIDATION,
            objective_text="Explain the MicroTwin validation.",
            run_id="module8-live-control",
        )
    )
    assert result.status == "COMPLETED"
    assert [step.tool_name for step in result.tool_calls] == [
        "get_microtwin_status",
        "get_microtwin_validation",
    ]
    assert all(step.execution_mode == "SUPERVISOR_REQUIRED_PREFETCH" for step in result.tool_calls)


def test_required_microtwin_model_selected_evidence_needs_every_tool(tmp_path: Path) -> None:
    supervisor = setup(
        tmp_path,
        [
            ProviderOutput(tool_call=ModelToolCall(name="get_microtwin_status", arguments={})),
            ProviderOutput(tool_call=ModelToolCall(name="get_microtwin_validation", arguments={})),
            ProviderOutput(text="Both required results were used."),
        ],
    )
    result = supervisor.run(
        SupervisorRequest(
            request_id="required-native",
            objective_type=ObjectiveType.EXPLAIN_MICROTWIN_VALIDATION,
            objective_text="Explain the MicroTwin validation.",
            run_id="module8-live-control",
        )
    )
    assert result.status == "COMPLETED"
    assert all(step.execution_mode == "MODEL_SELECTED_TOOL" for step in result.tool_calls)
