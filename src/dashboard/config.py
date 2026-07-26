"""Dashboard configuration and loopback enforcement."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]


@dataclass(frozen=True)
class DashboardConfig:
    root: Path
    host: str
    port: int
    maximum_items: int
    snapshot: Path
    static_root: Path
    template_root: Path


def require_loopback(host: str) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("dashboard_host_not_ip") from exc
    if not address.is_loopback or host != "127.0.0.1":
        raise ValueError("dashboard_host_not_approved_loopback")


def load_dashboard_config(path: Path) -> DashboardConfig:
    root = path.resolve().parents[1]
    raw = cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))["dashboard"]
    if raw["schema_version"] != 1 or not raw["read_only"] or raw["external_assets_allowed"]:
        raise ValueError("invalid_dashboard_policy")
    require_loopback(str(raw["host"]))
    port = int(raw["port"])
    if not 1024 <= port <= 65535:
        raise ValueError("invalid_dashboard_port")
    return DashboardConfig(
        root,
        str(raw["host"]),
        port,
        int(raw["maximum_items"]),
        root / str(raw["snapshot"]),
        root / str(raw["static_root"]),
        root / str(raw["template_root"]),
    )
