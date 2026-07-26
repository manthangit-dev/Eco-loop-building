"""Bounded native Ollama tool-call capability check."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.llm.config import load_llm_settings
from src.llm.local_provider import LocalOpenSourceProvider
from src.llm.models import ProviderMessage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/llm_supervisor.yaml"))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    provider = LocalOpenSourceProvider(load_llm_settings(args.config))
    schema = (
        {
            "type": "function",
            "function": {
                "name": "get_test_value",
                "description": "Return a deterministic local test value.",
                "parameters": {
                    "type": "object",
                    "properties": {"name": {"type": "string", "const": "smoke"}},
                    "required": ["name"],
                    "additionalProperties": False,
                },
            },
        },
    )
    messages = [
        ProviderMessage(
            role="system", content="Call the supplied tool once, then report its result."
        ),
        ProviderMessage(role="user", content="Use get_test_value with name smoke."),
    ]
    first = provider.generate_with_tools(messages, schema)
    call = first.tool_call
    valid = (
        call is not None and call.name == "get_test_value" and call.arguments == {"name": "smoke"}
    )
    final_text = ""
    if valid:
        messages += [
            ProviderMessage(role="assistant", content="Tool call accepted."),
            ProviderMessage(role="tool", content=json.dumps({"name": "smoke", "value": 42})),
        ]
        final_text = provider.generate_with_tools(messages, ()).text
    report = {
        "status": "PASS" if valid and bool(final_text.strip()) else "FAIL",
        "native_tool_call": valid,
        "json_fallback_attempted": False,
        "json_fallback_result": "NOT_REQUIRED" if valid else "NOT_ATTEMPTED",
        "tool_call": None if call is None else call.model_dump(),
        "final_response": final_text,
    }
    print(json.dumps(report, indent=2 if args.pretty else None))
    provider.close()
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
