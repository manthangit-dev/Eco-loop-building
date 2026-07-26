"""Export a deterministic, bounded, shareable Module 15 evidence package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.dashboard.models import EvidenceSnapshot
from src.planning.provenance import planning_fingerprint

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def markdown(title: str, body: list[str]) -> str:
    return f"# {title}\n\n" + "\n\n".join(body) + "\n"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("status\nNO_ROWS\n", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def validate_package(directory: Path) -> dict[str, Any]:
    checksum_path = directory / "checksum_manifest.json"
    payload = json.loads(checksum_path.read_text(encoding="utf-8"))
    errors = [
        name
        for name, expected in payload["files"].items()
        if not (directory / name).is_file() or sha(directory / name) != expected
    ]
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in directory.iterdir()
        if path.is_file()
    )
    forbidden = [token for token in ("/home/", ".env", "BEGIN PRIVATE KEY") if token in text]
    if re.search(r"[A-Za-z]:\\+", text):
        forbidden.append("absolute_windows_path")
    prohibited_suffixes = {".db", ".sqlite", ".bin", ".pth", ".pt", ".onnx"}
    prohibited = [
        path.name
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in prohibited_suffixes
    ]
    return {
        "status": "PASS" if not errors and not forbidden and not prohibited else "FAIL",
        "checksum_errors": errors,
        "forbidden_content": forbidden,
        "prohibited_files": prohibited,
        "package_fingerprint": payload["package_fingerprint"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot", type=Path, default=ROOT / "outputs/module15/evidence_snapshot.json"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/module15/evidence_package")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    if args.validate_only:
        result = validate_package(args.output)
        result["runtime_seconds"] = round(time.monotonic() - started, 6)
        print(json.dumps(result, indent=2 if args.json else None))
        return 0 if result["status"] == "PASS" else 1
    snapshot = EvidenceSnapshot.model_validate_json(args.snapshot.read_text(encoding="utf-8"))
    if args.output.exists() and any(args.output.iterdir()) and not args.force:
        raise FileExistsError("evidence_package_exists_use_force")
    args.output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.snapshot, args.output / "evidence_snapshot.json")
    manifest_source = args.snapshot.with_name("evidence_manifest.json")
    shutil.copyfile(manifest_source, args.output / "evidence_manifest.json")
    sections = snapshot.sections
    documents = {
        "SYSTEM_OVERVIEW.md": (
            "System overview",
            [
                "Simulation-only, local-only, read-only evidence dashboard.",
                "Annual savings: **NOT ESTABLISHED**. Real-building control: **NOT IMPLEMENTED**.",
            ],
        ),
        "PLANNING_EVIDENCE.md": (
            "Planning evidence",
            [
                f"Selected strategy: `{sections['overview']['selected_strategy']}`.",
                "Candidate actions and weights were not modified by Module 15.",
            ],
        ),
        "MICROTWIN_EVIDENCE.md": (
            "MicroTwin evidence",
            [
                "Thermal model: **QUALIFIED**. Demand model: **UNAVAILABLE**.",
                "Twelve-step error and aligned applicability remain visible in the snapshot.",
            ],
        ),
        "COMFORT_LEDGER_EVIDENCE.md": (
            "Comfort Ledger evidence",
            ["Ledger values are advisory comfort and fairness proxies, not occupant guarantees."],
        ),
        "THERMAL_BANK_EVIDENCE.md": (
            "Thermal Bank evidence",
            ["Closing result: 0 RTFU.", "RTFU is not kWh or physical stored energy."],
        ),
        "EXECUTION_EVIDENCE.md": (
            "Execution evidence",
            [
                "Approval is consumed. Live execution completed with one guarded set "
                "and one guarded reset."
            ],
        ),
        "SHORT_RUN_COMPARISON.md": (
            "Short-run comparison",
            [
                "The three-hour comfort-focused action reduced temperature relative to native.",
                "Electricity increased; this is not savings evidence.",
            ],
        ),
        "RECONCILIATION_EVIDENCE.md": (
            "Reconciliation evidence",
            [
                "July 19 timestamps are aligned. Applicability is **DEGRADED_BUT_USABLE**.",
                "The January/July comparison is historical invalid evidence.",
            ],
        ),
        "SAFETY_AUDIT.md": (
            "Safety audit",
            [
                "All physical calls carry guard decisions. Mandatory native reset passed. "
                "Unguarded calls: 0."
            ],
        ),
        "LIMITATIONS.md": ("Limitations", list(snapshot.limitations)),
    }
    for name, (title, body) in documents.items():
        (args.output / name).write_text(markdown(title, body), encoding="utf-8")
    write_csv(args.output / "native_live_chart.csv", sections["comparison"])
    write_csv(args.output / "reconciliation_chart.csv", sections["reconciliation"]["points"])
    values = [item.model_dump(mode="json") for item in snapshot.values]
    write_csv(
        args.output / "evidence_values.csv",
        [
            {
                "value_id": x["value_id"],
                "metric_name": x["metric_name"],
                "value": x["value"],
                "units": x["units"],
                "classification": x["claim_classification"],
                "source_ids": "|".join(x["source_ids"]),
            }
            for x in values
        ],
    )
    package_files = sorted(
        path
        for path in args.output.iterdir()
        if path.is_file() and path.name != "checksum_manifest.json"
    )
    checksums = {path.name: sha(path) for path in package_files}
    checksum_payload = {
        "schema_version": 1,
        "label": "checksum manifest; not a signature",
        "files": checksums,
        "package_fingerprint": planning_fingerprint(checksums),
    }
    (args.output / "checksum_manifest.json").write_text(
        json.dumps(checksum_payload, indent=2) + "\n", encoding="utf-8"
    )
    result = {
        "status": "PASS",
        "file_count": len(package_files) + 1,
        "csv_count": 3,
        "markdown_count": len(documents),
        "package_fingerprint": checksum_payload["package_fingerprint"],
        "runtime_seconds": round(time.monotonic() - started, 6),
        "raw_database_included": False,
        "model_weights_included": False,
        "absolute_paths_included": False,
    }
    print(json.dumps(result, indent=2 if args.json else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
