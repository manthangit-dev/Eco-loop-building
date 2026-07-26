"""Check local dashboard health, pages, assets, and read-only policy."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request

PAGES = (
    "/",
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


def request(url: str, method: str = "GET", timeout: float = 5) -> tuple[int, bytes, dict[str, str]]:
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, method=method), timeout=timeout
        ) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    parsed = urllib.parse.urlparse(args.url)
    if parsed.hostname != "127.0.0.1":
        raise ValueError("health_check_requires_loopback")
    started = time.monotonic()
    health_status, health_body, headers = request(args.url + "/api/health", timeout=args.timeout)
    health = json.loads(health_body) if health_body else {}
    health = health.get("data", health)
    page_results = {page: request(args.url + page, timeout=args.timeout)[0] for page in PAGES}
    methods = {
        method: request(args.url + "/api/health", method, args.timeout)[0]
        for method in ("POST", "PUT", "PATCH", "DELETE")
    }
    html = request(args.url + "/")[1].decode("utf-8")
    checks = {
        "health": health_status == 200 and health.get("status") == "PASS",
        "evidence_current": health.get("evidence_status") == "CURRENT",
        "pages": all(value == 200 for value in page_results.values()),
        "write_methods_rejected": all(value == 405 for value in methods.values()),
        "security_headers": all(
            name in headers
            for name in (
                "Content-Security-Policy",
                "X-Content-Type-Options",
                "X-Frame-Options",
                "Referrer-Policy",
            )
        ),
        "no_external_assets": "https://" not in html and "http://" not in html,
        "no_execution_route": request(args.url + "/api/execution/start")[0] == 404,
        "no_approval_route": request(args.url + "/api/approval/create")[0] == 404,
        "no_upload_route": request(args.url + "/api/upload")[0] == 404,
        "no_sql_route": request(args.url + "/api/sql")[0] == 404,
    }
    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "page_count": len(PAGES),
        "get_route_count": 19,
        "head_route_count": 19,
        "method_statuses": methods,
        "runtime_seconds": round(time.monotonic() - started, 6),
    }
    print(json.dumps(result, indent=2 if args.pretty or args.json else None))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
