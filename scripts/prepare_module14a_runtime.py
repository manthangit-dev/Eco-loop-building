"""Create the immutable derived one-day runtime IDF and alignment report."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.execution.alignment import load_alignment_settings, runtime_window
from src.execution.preflight import file_sha256

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    settings = load_alignment_settings(ROOT / "config/module14a.yaml")
    source = settings.parent_idf.read_text(encoding="utf-8")
    pattern = re.compile(r"  RunPeriod,.*?Yes;\s+!- Use Weather File Snow Indicators", re.DOTALL)
    replacement = """  RunPeriod,
    Module14A Context Aligned 2013-07-19,
    7,
    19,
    2013,
    7,
    19,
    2013,
    Friday,
    Yes,
    Yes,
    No,
    Yes,
    Yes;                     !- Use Weather File Snow Indicators"""
    derived, count = pattern.subn(replacement, source, count=1)
    if count != 1:
        raise RuntimeError("runperiod_not_found")
    native_schedule = "Until: 20:00,23.9,       !- Field 11"
    aligned_schedule = "Until: 20:00,28.4,       !- Field 11"
    if derived.count(native_schedule) != 1:
        raise RuntimeError("cooling_schedule_not_found")
    derived = derived.replace(native_schedule, aligned_schedule)
    settings.runtime_idf.parent.mkdir(parents=True, exist_ok=True)
    settings.runtime_idf.write_text(derived, encoding="utf-8")
    window = runtime_window(settings)
    report = {
        "status": "PASS",
        "path": "PATH_B",
        "path_reason": (
            "The original July 21 Sunday context has no cooling-relevant occupancy; "
            "a deterministic occupied July 19 baseline context is reproducible."
        ),
        "parent_idf": str(settings.parent_idf.relative_to(ROOT)),
        "parent_checksum": file_sha256(settings.parent_idf),
        "derived_idf": str(settings.runtime_idf.relative_to(ROOT)),
        "derived_idf_fingerprint": file_sha256(settings.runtime_idf),
        "epw_checksum": file_sha256(
            ROOT / "weather/input/USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"
        ),
        "runtime_window": window,
        "canonical_modified": False,
    }
    output = ROOT / "outputs/module14a/runtime_manifest.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
