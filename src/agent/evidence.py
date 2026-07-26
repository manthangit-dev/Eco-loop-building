"""Mechanical evidence reconciliation."""

from src.agent.models import Evidence
from src.mcp_server.models import ToolEnvelope


def reconcile(evidence: tuple[Evidence, ...], results: dict[str, ToolEnvelope]) -> None:
    for item in evidence:
        result = results.get(item.tool_call_id)
        if result is None or result.tool_name != item.tool_name or not result.success:
            raise ValueError("invalid_evidence_reference")
