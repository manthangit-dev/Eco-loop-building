"""Independent fixed MCP policy."""

from __future__ import annotations

from typing import Any

from src.mcp_server.models import ToolClassification, ToolDefinition

FORBIDDEN_FIELDS = frozenset(
    {"enable_control", "admin", "bypass_guard", "approved", "emergency", "system_override"}
)


class ToolPolicy:
    def __init__(self, registry: tuple[ToolDefinition, ...]) -> None:
        self.registry = {item.name: item for item in registry}

    @property
    def allowed_names(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, item in self.registry.items()
            if item.enabled and item.classification != ToolClassification.CONTROL_CAPABLE
        )

    def validate(self, name: str, arguments: dict[str, Any]) -> None:
        definition = self.registry.get(name)
        if definition is None:
            raise ValueError("unknown_tool")
        if (
            not definition.enabled
            or definition.classification == ToolClassification.CONTROL_CAPABLE
        ):
            raise PermissionError("denied_control_tool")
        hostile = FORBIDDEN_FIELDS.intersection(arguments)
        if hostile:
            raise PermissionError(f"forbidden_override_field:{sorted(hostile)[0]}")
