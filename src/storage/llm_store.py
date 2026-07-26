"""Transactional bounded LLM session audit."""

import sqlite3
from pathlib import Path

from src.agent.models import SupervisorRequest, SupervisorResponse
from src.mcp_server.models import fingerprint
from src.storage.llm_schema import migrate_llm_schema


class LLMStore:
    def __init__(self, path: Path, output_root: Path) -> None:
        resolved = path.resolve()
        resolved.relative_to(output_root.resolve())
        resolved.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(resolved)
        migrate_llm_schema(self.connection)

    def append(
        self,
        request: SupervisorRequest,
        response: SupervisorResponse,
        catalogue_fingerprint: str,
        prompt_version: int,
    ) -> SupervisorResponse:
        request_json = request.model_dump_json()
        existing = self.connection.execute(
            "SELECT response_json FROM llm_final_responses WHERE session_id=?",
            (response.session_id,),
        ).fetchone()
        if existing is not None:
            return SupervisorResponse.model_validate_json(existing[0])
        conflict = self.connection.execute(
            "SELECT session_id FROM llm_sessions WHERE request_id=?", (request.request_id,)
        ).fetchone()
        if conflict is not None:
            raise ValueError("conflicting_duplicate_session_request")
        response_json = response.model_dump_json()
        self.connection.execute("BEGIN")
        try:
            self.connection.execute(
                "INSERT INTO llm_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    response.session_id,
                    request.request_id,
                    request.objective_type.value,
                    response.provider,
                    response.model,
                    response.status,
                    request.run_id,
                    catalogue_fingerprint,
                    prompt_version,
                    response.schema_version,
                    int(response.provider == "deterministic_mock"),
                    0,
                    len(response.tool_calls) + 1,
                    len(response.tool_calls),
                    len(response.warnings),
                    (len(request_json) + 3) // 4,
                    (len(response_json) + 3) // 4,
                ),
            )
            for index, step in enumerate(response.tool_calls):
                self.connection.execute(
                    "INSERT INTO llm_tool_steps VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        response.session_id,
                        index,
                        step.tool_call_id,
                        step.tool_name,
                        "{}",
                        step.tool_call_id,
                        int(step.success),
                        None,
                        int(step.reused),
                    ),
                )
            self.connection.execute(
                "INSERT INTO llm_final_responses VALUES(?,?,?,?,0)",
                (
                    response.session_id,
                    response_json,
                    fingerprint(response.model_dump(mode="json")),
                    "PASS",
                ),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return response

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "LLMStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
