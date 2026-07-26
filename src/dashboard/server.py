"""Standard-library loopback-only, read-only dashboard server."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.dashboard.config import load_dashboard_config, require_loopback
from src.dashboard.evidence import validate_snapshot
from src.dashboard.models import EvidenceSnapshot
from src.dashboard.security import SECURITY_HEADERS

ROOT = Path(__file__).resolve().parents[2]
PAGE_ROUTES = (
    "/",
    "/overview",
    "/planning",
    "/microtwin",
    "/ledger",
    "/thermal-bank",
    "/execution",
    "/comparison",
    "/reconciliation",
    "/audit",
    "/evidence",
    "/limitations",
)


class DashboardHandler(BaseHTTPRequestHandler):
    snapshot: EvidenceSnapshot
    root: Path
    static_root: Path
    maximum_items: int = 100
    server_version = "ThermoLedgerEvidence/1"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Allow", "GET, HEAD")
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        self.end_headers()

    def _send(
        self, payload: bytes, content_type: str, status: int = 200, head: bool = False
    ) -> None:
        self._headers(status, content_type, len(payload))
        if not head:
            self.wfile.write(payload)

    def _json(self, data: Any, status: int = 200, head: bool = False) -> None:
        payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        self._send(payload, "application/json; charset=utf-8", status, head)

    def _error(self, status: int, code: str, head: bool = False) -> None:
        self._json({"schema_version": 1, "status": "ERROR", "error": code}, status, head)

    def _bounded(self, values: list[Any], query: dict[str, list[str]]) -> dict[str, Any]:
        try:
            limit = int(query.get("limit", ["50"])[0])
            cursor = int(query.get("cursor", ["0"])[0])
        except ValueError as exc:
            raise ValueError("invalid_pagination") from exc
        if not 1 <= limit <= self.maximum_items or cursor < 0:
            raise ValueError("invalid_pagination")
        items = values[cursor : cursor + limit]
        next_cursor = cursor + len(items) if cursor + len(items) < len(values) else None
        return {
            "schema_version": 1,
            "items": items,
            "count": len(items),
            "total": len(values),
            "next_cursor": next_cursor,
        }

    def _api(self, path: str, query: dict[str, list[str]]) -> Any:
        sections = self.snapshot.sections
        routes: dict[str, Any] = {
            "/api/health": {
                "schema_version": 1,
                "status": "PASS",
                "evidence_status": "CURRENT",
                "database_status": "PASS",
                "read_only": True,
                "simulation_only": True,
            },
            "/api/overview": sections["overview"],
            "/api/modules": sections["modules"],
            "/api/planning/context": sections["planning"]["context"],
            "/api/planning/candidates": sections["planning"]["candidates"],
            "/api/microtwin/status": {
                "status": sections["microtwin"]["status"],
                "demand_model": sections["microtwin"]["demand_model"],
            },
            "/api/microtwin/validation": sections["microtwin"]["validation"],
            "/api/microtwin/rollouts": sections["microtwin"]["rollouts"],
            "/api/ledger/evaluations": sections["ledger"]["evaluations"],
            "/api/ledger/ranking": sections["ledger"]["ranking"],
            "/api/thermal-bank/status": sections["thermal_bank"],
            "/api/execution/approval": sections["execution"]["approval"],
            "/api/execution/session": {
                **sections["execution"]["session"],
                "state_transitions": sections["execution"]["state_transitions"],
                "transition_scope": sections["execution"]["transition_scope"],
            },
            "/api/execution/actions": sections["execution"]["actions"],
            "/api/execution/comparison": sections["comparison"],
            "/api/reconciliation": sections["reconciliation"],
            "/api/audit": sections["audit"],
            "/api/limitations": sections["limitations"],
            "/api/manifest": {
                "schema_version": 1,
                "snapshot_fingerprint": self.snapshot.snapshot_fingerprint,
                "source_count": len(self.snapshot.sources),
                "value_count": len(self.snapshot.values),
            },
        }
        if path.startswith("/api/evidence/"):
            evidence_id = path.rsplit("/", 1)[-1]
            for source in self.snapshot.sources:
                if source.evidence_source_id == evidence_id:
                    return source.model_dump(mode="json")
            for value in self.snapshot.values:
                if value.value_id == evidence_id:
                    return value.model_dump(mode="json")
            raise KeyError("unknown_evidence_id")
        if path not in routes:
            raise KeyError("unknown_route")
        result = routes[path]
        if isinstance(result, list):
            return self._bounded(result, query)
        return {"schema_version": 1, "data": result}

    def _handle(self, head: bool = False) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/"):
                self._json(self._api(parsed.path, parse_qs(parsed.query)), head=head)
                return
            if parsed.path in PAGE_ROUTES:
                payload = (self.root / "src/dashboard/templates/index.html").read_bytes()
                self._send(payload, "text/html; charset=utf-8", head=head)
                return
            if parsed.path.startswith("/static/"):
                relative = parsed.path.removeprefix("/static/")
                target = (self.static_root / relative).resolve()
                target.relative_to(self.static_root.resolve())
                if not target.is_file():
                    raise KeyError("static_not_found")
                self._send(
                    target.read_bytes(),
                    mimetypes.guess_type(target.name)[0] or "application/octet-stream",
                    head=head,
                )
                return
            self._error(HTTPStatus.NOT_FOUND, "not_found", head)
        except KeyError as exc:
            self._error(HTTPStatus.NOT_FOUND, str(exc.args[0]), head)
        except ValueError as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc), head)
        except (OSError, TypeError) as exc:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, type(exc).__name__, head)

    def do_GET(self) -> None:
        self._handle()

    def do_HEAD(self) -> None:
        self._handle(head=True)

    def _reject_write(self) -> None:
        self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed")

    do_POST = _reject_write
    do_PUT = _reject_write
    do_PATCH = _reject_write
    do_DELETE = _reject_write


def make_handler(
    snapshot: EvidenceSnapshot, root: Path, maximum_items: int = 100
) -> type[DashboardHandler]:
    class BoundHandler(DashboardHandler):
        pass

    BoundHandler.snapshot = snapshot
    BoundHandler.root = root
    BoundHandler.static_root = root / "src/dashboard/static"
    BoundHandler.maximum_items = maximum_items
    return BoundHandler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int)
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args()
    config = load_dashboard_config(ROOT / "config/dashboard.yaml")
    require_loopback(args.host)
    snapshot_path = args.snapshot or config.snapshot
    snapshot = EvidenceSnapshot.model_validate_json(snapshot_path.read_text(encoding="utf-8"))
    errors = validate_snapshot(ROOT, snapshot)
    if errors:
        raise ValueError(f"stale_dashboard_evidence:{errors}")
    port = args.port or config.port
    server = ThreadingHTTPServer(
        (args.host, port), make_handler(snapshot, ROOT, config.maximum_items)
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "url": f"http://{args.host}:{port}",
                "read_only": True,
                "evidence": "CURRENT",
            }
        ),
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
