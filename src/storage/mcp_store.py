"""Transactional idempotent MCP audit storage."""

import sqlite3
from pathlib import Path

from src.mcp_server.models import (
    ToolDefinition,
    ToolEnvelope,
    ToolRequest,
    canonical_json,
    fingerprint,
)
from src.storage.mcp_schema import migrate_mcp_schema


class MCPAuditStore:
    def __init__(self, path: Path, approved_root: Path) -> None:
        resolved = path.resolve()
        resolved.relative_to(approved_root.resolve())
        resolved.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(resolved)
        self.connection.execute("PRAGMA foreign_keys=ON")
        migrate_mcp_schema(self.connection)
        self.order = int(
            self.connection.execute(
                "SELECT COALESCE(MAX(deterministic_order),0) FROM mcp_tool_calls"
            ).fetchone()[0]
        )

    def existing(self, request: ToolRequest) -> ToolEnvelope | None:
        row = self.connection.execute(
            "SELECT request_fingerprint,response_json FROM mcp_tool_calls WHERE request_id=?",
            (request.request_id,),
        ).fetchone()
        if row is None:
            return None
        if str(row[0]) != fingerprint(request.model_dump(mode="json")):
            raise ValueError("conflicting_duplicate")
        return ToolEnvelope.model_validate_json(str(row[1]))

    def append(
        self, request: ToolRequest, definition: ToolDefinition, response: ToolEnvelope
    ) -> None:
        self.connection.execute("BEGIN")
        try:
            self.order += 1
            request_payload = request.model_dump(mode="json")
            response_payload = response.model_dump(mode="json")
            self.connection.execute(
                "INSERT INTO mcp_tool_calls VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    response.tool_call_id,
                    request.request_id,
                    request.tool_name,
                    definition.classification.value,
                    canonical_json(request_payload),
                    canonical_json(response_payload),
                    int(response.success),
                    response.run_id,
                    fingerprint(request_payload),
                    response.fingerprint,
                    self.order,
                ),
            )
            for index, error in enumerate(response.errors):
                self.connection.execute(
                    "INSERT INTO mcp_tool_errors VALUES(?,?,?,?,?,?)",
                    (
                        f"{response.tool_call_id}:{index}",
                        response.tool_call_id,
                        index,
                        error.code,
                        error.message,
                        error.field,
                    ),
                )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "MCPAuditStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
