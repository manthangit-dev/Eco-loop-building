from pathlib import Path

from src.mcp_server.config import load_mcp_settings
from src.mcp_server.models import ToolRequest
from src.mcp_server.service import MCPToolService


def test_audit_idempotency_integrity_and_foreign_keys(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    settings = load_mcp_settings(root / "config/mcp_server.yaml")
    from dataclasses import replace

    settings = replace(settings, output_root=tmp_path, audit_database=tmp_path / "audit.db")
    service = MCPToolService(settings)
    request = ToolRequest(request_id="same", tool_name="list_available_runs", arguments={})
    assert service.call(request) == service.call(request)
    import sqlite3

    connection = sqlite3.connect(settings.audit_database)
    assert connection.execute("SELECT COUNT(*) FROM mcp_tool_calls").fetchone()[0] == 1
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
