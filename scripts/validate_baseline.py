"""Validate completed Module 2 EnergyPlus baseline outputs without running EnergyPlus."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

GENERATED_SUFFIXES = {
    ".csv",
    ".eio",
    ".end",
    ".err",
    ".eso",
    ".htm",
    ".html",
    ".mdd",
    ".mtd",
    ".mtr",
    ".rdd",
    ".rvaudit",
    ".sql",
}
SUMMARY_PATTERN = re.compile(
    r"(?P<warnings>\d+)\s+Warning(?:s)?;\s*"
    r"(?P<severe>\d+)\s+Severe Errors?",
    re.IGNORECASE,
)


class Status(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class Check:
    name: str
    status: Status
    detail: str
    remediation: str = ""


@dataclass(frozen=True)
class ErrorCounts:
    warnings: int
    severe: int
    fatal: int
    used_final_summary: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return data


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def parse_error_summary(text: str) -> ErrorCounts:
    """Prefer the final EnergyPlus summary and avoid double-counting detailed messages."""
    summaries = list(SUMMARY_PATTERN.finditer(text))
    if summaries:
        final = summaries[-1]
        warnings = int(final.group("warnings"))
        severe = int(final.group("severe"))
        used_summary = True
    else:
        warnings = len(re.findall(r"^\s*\*\*\s*Warning\s*\*\*", text, re.MULTILINE | re.I))
        severe = len(re.findall(r"^\s*\*\*\s*Severe\s*\*\*", text, re.MULTILINE | re.I))
        used_summary = False
    fatal = len(re.findall(r"^\s*\*\*\s*Fatal\s*\*\*", text, re.MULTILINE | re.I))
    if "Fatal Error Detected" in text and fatal == 0:
        fatal = 1
    return ErrorCounts(warnings, severe, fatal, used_summary)


def check_file(path: Path, name: str, required: bool = True) -> Check:
    if not path.is_file():
        status = Status.FAIL if required else Status.WARN
        return Check(name, status, f"Missing: {path}", f"Regenerate {path.name}.")
    if path.stat().st_size == 0:
        status = Status.FAIL if required else Status.WARN
        return Check(name, status, f"Empty: {path}", f"Regenerate non-empty {path.name}.")
    return Check(name, Status.PASS, f"{path.name}: {path.stat().st_size} bytes")


def check_checksum(path: Path, expected: str, name: str) -> Check:
    if not path.is_file():
        return Check(name, Status.FAIL, f"Missing: {path}", "Restore the preserved input.")
    actual = sha256_file(path)
    if actual.lower() != expected.lower():
        return Check(
            name,
            Status.FAIL,
            f"Checksum mismatch for {path}",
            "Restore the verified model or weather file; do not edit it in place.",
        )
    return Check(name, Status.PASS, f"SHA-256 verified: {actual}")


def is_safe_output_directory(output: Path, allowed_root: Path) -> bool:
    try:
        output.resolve().relative_to(allowed_root.resolve())
    except ValueError:
        return False
    return output.resolve() != allowed_root.resolve()


def generated_files(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file()
        and (path.suffix.lower() in GENERATED_SUFFIXES or path.name.lower().startswith("eplusout."))
    )


def validation_exit_code(checks: Sequence[Check]) -> int:
    return 1 if any(check.status is Status.FAIL for check in checks) else 0


def _pass_fail(name: str, condition: bool, detail: str, remediation: str) -> Check:
    return Check(
        name,
        Status.PASS if condition else Status.FAIL,
        detail,
        "" if condition else remediation,
    )


def validate_run(
    config_path: Path,
    output_override: Path | None = None,
    allowed_root_override: Path | None = None,
) -> tuple[list[Check], Path]:
    root = config_path.resolve().parents[1]
    config = load_yaml(config_path)
    manifest = load_manifest(root / "models" / "MODEL_MANIFEST.json")
    baseline = config["baseline"]
    validation = config["validation"]
    allowed_root = allowed_root_override or root / "data" / "output" / "module_2_baseline"
    output = output_override or root / baseline["output_directory"]
    checks: list[Check] = []

    safe = is_safe_output_directory(output, allowed_root)
    checks.append(
        _pass_fail(
            "Output directory safety",
            safe,
            (
                f"Output is inside dedicated root: {output}"
                if safe
                else f"Unsafe output path: {output}"
            ),
            f"Use a child directory of {allowed_root}.",
        )
    )
    if not output.is_dir():
        checks.append(
            Check("Output directory", Status.FAIL, f"Missing: {output}", "Run run_baseline.ps1.")
        )
        return checks, output
    checks.append(Check("Output directory", Status.PASS, f"Found: {output}"))

    metadata_path = output / "run_metadata.json"
    metadata_check = check_file(metadata_path, "Process metadata")
    checks.append(metadata_check)
    metadata: dict[str, Any] = {}
    if metadata_check.status is Status.PASS:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
        code = metadata.get("energyplus_exit_code", metadata.get("exit_code"))
        checks.append(
            _pass_fail(
                "EnergyPlus exit code",
                code == 0,
                f"Recorded exit code: {code}",
                "Inspect the EnergyPlus error report and rerun.",
            )
        )

    prefix = str(baseline["output_prefix"])
    error_path = output / f"{prefix}.err"
    error_check = check_file(error_path, "Error report")
    checks.append(error_check)
    if error_check.status is Status.PASS:
        counts = parse_error_summary(error_path.read_text(encoding="utf-8", errors="replace"))
        checks.extend(
            [
                _pass_fail(
                    "Fatal errors",
                    counts.fatal == 0,
                    f"Fatal errors: {counts.fatal}",
                    "Resolve fatal EnergyPlus errors before accepting the baseline.",
                ),
                _pass_fail(
                    "Severe errors",
                    counts.severe == 0,
                    f"Severe errors: {counts.severe}",
                    "Resolve severe EnergyPlus errors before accepting the baseline.",
                ),
                Check(
                    "Warnings",
                    Status.WARN if counts.warnings else Status.PASS,
                    f"Warnings: {counts.warnings}; final summary used: {counts.used_final_summary}",
                    "Review warnings in the error report." if counts.warnings else "",
                ),
            ]
        )

    for filename in validation["required_output_files"]:
        if filename == error_path.name:
            continue
        checks.append(check_file(output / filename, f"Required output {filename}"))
    for filename in validation.get("optional_dictionary_files", []):
        checks.append(check_file(output / filename, f"Dictionary {filename}", required=False))

    non_empty_results = [
        path
        for path in output.iterdir()
        if path.is_file() and path.stat().st_size > 0 and path.suffix.lower() in GENERATED_SUFFIXES
    ]
    minimum = int(validation["minimum_non_empty_output_files"])
    checks.append(
        _pass_fail(
            "Non-empty result count",
            len(non_empty_results) >= minimum,
            f"Found {len(non_empty_results)} non-empty result files; minimum is {minimum}.",
            "Enable required reporting outputs and rerun EnergyPlus.",
        )
    )

    source_path = root / baseline["source_model"]
    baseline_path = root / baseline["baseline_model"]
    weather_path = root / "weather" / "input" / manifest["weather_filename"]
    checks.extend(
        [
            check_checksum(
                source_path, manifest["repository_source_copy_sha256"], "Source checksum"
            ),
            check_checksum(baseline_path, manifest["derived_baseline_sha256"], "Baseline checksum"),
            check_checksum(weather_path, manifest["weather_sha256"], "Weather checksum"),
        ]
    )
    source_outputs = generated_files(source_path.parent)
    checks.append(
        _pass_fail(
            "Source directory cleanliness",
            not source_outputs,
            f"Generated files in source directory: {source_outputs}",
            "Run simulations only in the configured output directory.",
        )
    )
    before = metadata.get("installation_generated_files_before", [])
    after = metadata.get("installation_generated_files_after", [])
    checks.append(
        _pass_fail(
            "EnergyPlus installation cleanliness",
            before == after,
            f"Installation generated-file snapshot unchanged: {before == after}",
            "Remove only confirmed simulation outputs from the installation after manual review.",
        )
    )

    summary = {
        "status": "PASS" if validation_exit_code(checks) == 0 else "FAIL",
        "checks": [asdict(check) for check in checks],
        "generated_files": [
            {"name": path.name, "size_bytes": path.stat().st_size}
            for path in sorted(output.iterdir())
            if path.is_file()
        ],
    }
    (output / "validation_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return checks, output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/baseline.yaml"))
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--allowed-output-root", type=Path)
    args = parser.parse_args(argv)
    checks, output = validate_run(args.config, args.output_directory, args.allowed_output_root)
    for check in checks:
        print(f"[{check.status.value}] {check.name}: {check.detail}")
        if check.remediation and check.status is not Status.PASS:
            print(f"       Remediation: {check.remediation}")
    passed = sum(check.status is Status.PASS for check in checks)
    warned = sum(check.status is Status.WARN for check in checks)
    failed = sum(check.status is Status.FAIL for check in checks)
    print(f"\nSummary: {passed} passed, {warned} warned, {failed} failed.")
    print(f"Validated output directory: {output}")
    return validation_exit_code(checks)


if __name__ == "__main__":
    raise SystemExit(main())
