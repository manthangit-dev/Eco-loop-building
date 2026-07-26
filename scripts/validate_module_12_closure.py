"""Validate cached Module 12A closure evidence without EnergyPlus or retraining."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mcp_server.config import load_mcp_settings
from src.mcp_server.registry import build_registry
from src.microtwin.config import load_microtwin_settings

ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def main() -> int:
    yaml_files = sorted((*ROOT.glob("config/*.yaml"), *ROOT.glob("scenarios/**/*.yaml")))
    replay_1_path = ROOT / "outputs/module12b/replay_run_1.json"
    replay_2_path = ROOT / "outputs/module12b/replay_run_2.json"
    smoke_path = ROOT / "data/output/module_12_microtwin/real_model_smoke.json"
    json_files = (
        ROOT / "tests/fixtures/microtwin/module12_replay_manifest.json",
        replay_1_path,
        replay_2_path,
        ROOT / "outputs/module12b/replay_comparison.json",
        smoke_path,
    )
    for path in yaml_files:
        yaml.safe_load(path.read_text(encoding="utf-8"))
    for path in json_files:
        _load_json(path)
    replay_1, replay_2 = _load_json(replay_1_path), _load_json(replay_2_path)
    smoke = _load_json(smoke_path)
    settings = load_microtwin_settings(ROOT / "config/microtwin.yaml")
    model_manifest = _load_json(settings.model_directory / "model_manifest.json")
    project_manifest = _load_json(ROOT / "models/MODEL_MANIFEST.json")
    checksum_paths = {
        "source": ROOT / "models/source/5ZoneAirCooled_v26_1_original.idf",
        "baseline": ROOT / "models/baseline/thermoledger_5zone_baseline.idf",
        "weather": ROOT / "weather/input" / project_manifest["weather_filename"],
    }
    checksum_expected = {
        "source": project_manifest["repository_source_copy_sha256"],
        "baseline": project_manifest["derived_baseline_sha256"],
        "weather": project_manifest["weather_sha256"],
    }
    checksum_ok = all(
        hashlib.sha256(checksum_paths[name].read_bytes()).hexdigest() == checksum_expected[name]
        for name in checksum_paths
    )
    with sqlite3.connect(settings.database) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    tools = build_registry(load_mcp_settings(ROOT / "config/mcp_server.yaml").control_tools_enabled)
    required = [set(item) for item in smoke["required_tools"]]
    sessions = smoke["sessions"]
    evidence_ok = all(
        required[index] <= set(session["tools"])
        and session["evidence_validation"]
        and not session["physical_write_performed"]
        for index, session in enumerate(sessions)
    )
    checks = {
        "yaml_json": bool(yaml_files) and bool(json_files),
        "artifact_qualified": model_manifest["thermal_qualification"] is True,
        "candidate_preflight": _load_json(
            ROOT / "outputs/module12/module11_candidate_preflight.json"
        )["status"] == "PASS",
        "replay_105_twice": replay_1["scenario_count"] == replay_2["scenario_count"] >= 105,
        "replay_pass": replay_1["status"] == replay_2["status"] == "PASS",
        "replay_deterministic": replay_1["replay_fingerprint"] == replay_2["replay_fingerprint"],
        "required_evidence": smoke["status"] == "PASS" and evidence_ok,
        "zero_writes": replay_1["physical_write_count"] == smoke["physical_write_count"] == 0,
        "catalogue_v5_44": len(tools) == 44,
        "control_disabled": not tools[-1].enabled,
        "database_integrity": integrity == "ok",
        "foreign_keys": not foreign_keys,
        "idf_epw_checksums": checksum_ok,
        "documentation": (ROOT / "docs/MICROTWIN_REPLAY_COVERAGE.md").is_file(),
    }
    report = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}
    output = ROOT / "outputs/module12/closure_validation.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
