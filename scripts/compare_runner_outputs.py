"""Compare Module 2 CLI and Module 3 API outputs for structural parity."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.validate_baseline import parse_error_summary, sha256_file  # noqa: E402


@dataclass(frozen=True)
class CsvShape:
    header: list[str]
    row_count: int
    first_timestamp: str
    last_timestamp: str
    sha256: str


@dataclass(frozen=True)
class Comparison:
    name: str
    matches: bool
    module_2: Any
    module_3: Any
    detail: str


def csv_shape(path: Path) -> CsvShape:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        first = ""
        last = ""
        count = 0
        for row in reader:
            if not row:
                continue
            count += 1
            timestamp = row[0].strip()
            if not first:
                first = timestamp
            last = timestamp
    return CsvShape(header, count, first, last, sha256_file(path))


def comparison_exit_code(comparisons: Sequence[Comparison]) -> int:
    return 1 if any(not item.matches for item in comparisons) else 0


def compare_outputs(
    module_2: Path,
    module_3: Path,
    prefix: str,
    model_sha256: str,
    weather_sha256: str,
) -> list[Comparison]:
    metadata_2 = json.loads((module_2 / "run_metadata.json").read_text(encoding="utf-8-sig"))
    metadata_3 = json.loads((module_3 / "run_metadata.json").read_text(encoding="utf-8-sig"))
    counts_2 = parse_error_summary(
        (module_2 / f"{prefix}.err").read_text(encoding="utf-8", errors="replace")
    )
    counts_3 = parse_error_summary(
        (module_3 / f"{prefix}.err").read_text(encoding="utf-8", errors="replace")
    )
    csv_2 = csv_shape(module_2 / f"{prefix}.csv")
    csv_3 = csv_shape(module_3 / f"{prefix}.csv")
    required = [".err", ".eio", ".csv", ".htm", ".sql", ".rdd", ".mdd"]

    def existing_types(directory: Path) -> list[str]:
        return sorted(
            suffix
            for suffix in required
            if any(
                path.is_file() and path.stat().st_size > 0
                for path in directory.glob(f"*{suffix}")
            )
        )

    version_2 = str(metadata_2.get("energyplus_version", ""))
    version_3 = str(metadata_3.get("energyplus_version", ""))
    completion_2 = "Completed Successfully" in (
        module_2 / f"{prefix}.err"
    ).read_text(encoding="utf-8", errors="replace")
    completion_3 = "Completed Successfully" in (
        module_3 / f"{prefix}.err"
    ).read_text(encoding="utf-8", errors="replace")
    sql_2 = module_2 / f"{prefix}.sql"
    sql_3 = module_3 / f"{prefix}.sql"

    def size_or_zero(path: Path) -> int:
        return path.stat().st_size if path.is_file() else 0

    values = [
        ("EnergyPlus version", "26.1" in version_2 and "26.1" in version_3, version_2, version_3),
        (
            "Input model checksum",
            metadata_3.get("model_sha256") == model_sha256,
            model_sha256,
            metadata_3.get("model_sha256"),
        ),
        (
            "Weather checksum",
            metadata_3.get("weather_sha256") == weather_sha256,
            weather_sha256,
            metadata_3.get("weather_sha256"),
        ),
        (
            "Exit code",
            metadata_2.get("energyplus_exit_code", metadata_2.get("exit_code"))
            == metadata_3.get("exit_code")
            == 0,
            metadata_2.get("energyplus_exit_code", metadata_2.get("exit_code")),
            metadata_3.get("exit_code"),
        ),
        (
            "Warning count",
            counts_2.warnings == counts_3.warnings,
            counts_2.warnings,
            counts_3.warnings,
        ),
        ("Severe count", counts_2.severe == counts_3.severe, counts_2.severe, counts_3.severe),
        ("Fatal count", counts_2.fatal == counts_3.fatal, counts_2.fatal, counts_3.fatal),
        (
            "Required output types",
            existing_types(module_2) == existing_types(module_3),
            existing_types(module_2),
            existing_types(module_3),
        ),
        ("CSV header", csv_2.header == csv_3.header, csv_2.header, csv_3.header),
        ("CSV row count", csv_2.row_count == csv_3.row_count, csv_2.row_count, csv_3.row_count),
        (
            "First timestamp",
            csv_2.first_timestamp == csv_3.first_timestamp,
            csv_2.first_timestamp,
            csv_3.first_timestamp,
        ),
        (
            "Last timestamp",
            csv_2.last_timestamp == csv_3.last_timestamp,
            csv_2.last_timestamp,
            csv_3.last_timestamp,
        ),
        ("Run completion", completion_2 and completion_3, completion_2, completion_3),
        (
            "SQL output",
            all(
                path.is_file() and path.stat().st_size > 0 for path in (sql_2, sql_3)
            ),
            size_or_zero(sql_2),
            size_or_zero(sql_3),
        ),
    ]
    comparisons = [
        Comparison(name, matches, left, right, "match" if matches else "structural mismatch")
        for name, matches, left, right in values
    ]
    comparisons.append(
        Comparison(
            "CSV SHA-256",
            True,
            csv_2.sha256,
            csv_3.sha256,
            (
                "byte-identical"
                if csv_2.sha256 == csv_3.sha256
                else "hashes differ; structure compared"
            ),
        )
    )
    return comparisons


def run_comparison(config_path: Path) -> tuple[list[Comparison], Path]:
    root = config_path.resolve().parents[1]
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    manifest = json.loads((root / "models/MODEL_MANIFEST.json").read_text(encoding="utf-8"))
    paths = config["paths"]
    output = root / paths["module_3_output"]
    comparisons = compare_outputs(
        root / paths["module_2_output"],
        output,
        str(config["runner"]["output_prefix"]),
        str(manifest["derived_baseline_sha256"]),
        str(manifest["weather_sha256"]),
    )
    summary = {
        "status": "PASS" if comparison_exit_code(comparisons) == 0 else "FAIL",
        "comparisons": [asdict(item) for item in comparisons],
    }
    summary_path = output / "comparison_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return comparisons, summary_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/api_runner.yaml"))
    args = parser.parse_args(argv)
    comparisons, summary_path = run_comparison(args.config)
    for item in comparisons:
        label = "PASS" if item.matches else "FAIL"
        print(f"[{label}] {item.name}: {item.detail}")
    code = comparison_exit_code(comparisons)
    print(f"Comparison summary: {summary_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
