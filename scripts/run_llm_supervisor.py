"""Execute one bounded supervisor request using mock or configured local provider."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent.models import SupervisorRequest  # noqa: E402
from src.agent.supervisor import Supervisor  # noqa: E402
from src.llm.config import load_llm_settings  # noqa: E402
from src.llm.local_provider import LocalOpenSourceProvider  # noqa: E402
from src.llm.mock_provider import DeterministicMockProvider  # noqa: E402
from src.llm.models import ModelToolCall, ProviderOutput  # noqa: E402
from src.llm.provider import LLMProvider  # noqa: E402
from src.mcp_server.config import load_mcp_settings  # noqa: E402
from src.mcp_server.service import MCPToolService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path, nargs="?")
    parser.add_argument("--input-file", type=Path)
    parser.add_argument("--provider", choices=("mock", "local"), default="mock")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    input_path = args.input_file or args.request
    if input_path is None:
        parser.error("request or --input-file is required")
    try:
        request = SupervisorRequest.model_validate_json(input_path.read_text(encoding="utf-8"))
        root = Path(__file__).resolve().parents[1]
        settings = load_llm_settings(root / "config/llm_supervisor.yaml")
        if args.provider == "local":
            provider: LLMProvider = LocalOpenSourceProvider(settings)
        else:
            tool = "get_building_state"
            arguments: dict[str, object] = {"run_id": request.run_id}
            if request.objective_type.value == "EXPLAIN_CONTROLLER_STATUS":
                tool, arguments = "get_controller_status", {}
            elif request.zone:
                tool, arguments = "get_zone_state", {**arguments, "zone": request.zone}
            provider = DeterministicMockProvider(
                [
                    ProviderOutput(tool_call=ModelToolCall(name=tool, arguments=arguments)),
                    ProviderOutput(
                        text="Recorded evidence was retrieved; no physical action occurred."
                    ),
                ]
            )
        service = MCPToolService(load_mcp_settings(root / "config/mcp_server.yaml"))
        response = Supervisor(settings, provider, service).run(request)
        print(response.model_dump_json(indent=2 if args.pretty else None))
        provider.close()
        return 0 if response.status == "COMPLETED" else 3
    except Exception as exc:
        print(f"LLM supervisor failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
