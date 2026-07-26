from __future__ import annotations

import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from src.dashboard.claims import validate_claim
from src.dashboard.config import load_dashboard_config, require_loopback
from src.dashboard.evidence import build_snapshot, validate_snapshot
from src.dashboard.models import ClaimClassification
from src.dashboard.security import SECURITY_HEADERS, contains_external_reference
from src.dashboard.server import make_handler

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def snapshot():  # type: ignore[no-untyped-def]
    return build_snapshot(ROOT)


def test_dashboard_config_is_loopback_read_only() -> None:
    config = load_dashboard_config(ROOT / "config/dashboard.yaml")
    assert config.host == "127.0.0.1" and config.port == 8765
    for host in ("0.0.0.0", "192.168.1.4", "8.8.8.8"):
        with pytest.raises(ValueError, match="not_approved_loopback"):
            require_loopback(host)


def test_snapshot_has_provenance_and_is_current(snapshot) -> None:  # type: ignore[no-untyped-def]
    assert validate_snapshot(ROOT, snapshot) == []
    assert len(snapshot.sources) == 13 and len(snapshot.values) == 17
    assert all(
        item.source_ids and item.units and item.calculation_method for item in snapshot.values
    )
    assert len({item.claim_classification for item in snapshot.values}) == 7


@pytest.mark.parametrize(
    "text",
    [
        "annual savings achieved",
        "guaranteed comfort",
        "real-building savings",
        "RTFU is physical energy in kWh",
    ],
)
def test_unsupported_claims_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        validate_claim(text, ClaimClassification.VERIFIED_REPOSITORY_FACT)


def test_supported_claim_is_accepted() -> None:
    validate_claim("Annual savings are not established", ClaimClassification.NOT_ESTABLISHED)


def test_local_assets_and_security_policy() -> None:
    html = (ROOT / "src/dashboard/templates/index.html").read_text(encoding="utf-8")
    css = (ROOT / "src/dashboard/static/css/dashboard.css").read_text(encoding="utf-8")
    js = (ROOT / "src/dashboard/static/js/dashboard.js").read_text(encoding="utf-8")
    assert not any(contains_external_reference(item) for item in (html, css, js))
    assert "frame-ancestors 'none'" in SECURITY_HEADERS["Content-Security-Policy"]
    assert "viewport" in html and "Skip to evidence" in html and "aria-describedby" in html


def _request(url: str, method: str = "GET") -> tuple[int, dict[str, str]]:
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, method=method), timeout=3
        ) as response:
            return response.status, dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers)


def test_live_server_read_only_policy(snapshot) -> None:  # type: ignore[no-untyped-def]
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(snapshot, ROOT))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        status, headers = _request(url + "/api/health")
        assert status == 200 and "Content-Security-Policy" in headers
        assert _request(url + "/")[0] == 200
        assert _request(url + "/api/evidence/effect")[0] == 200
        assert _request(url + "/api/evidence/unknown")[0] == 404
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            assert _request(url + "/api/health", method)[0] == 405
        for forbidden in (
            "/api/execution/start",
            "/api/approval/create",
            "/api/upload",
            "/api/sql",
        ):
            assert _request(url + forbidden)[0] == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    assert not thread.is_alive()
