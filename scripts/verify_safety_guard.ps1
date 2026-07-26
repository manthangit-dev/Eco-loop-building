$ErrorActionPreference = "Stop"
$Python = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
function Assert-NativeSuccess {
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& $Python --version
Assert-NativeSuccess
& $Python scripts/check_environment.py
Assert-NativeSuccess
& $Python -B -m pytest -p no:cacheprovider
Assert-NativeSuccess
& $Python -m ruff check . --no-cache
Assert-NativeSuccess
& $Python -m mypy --no-incremental src scripts tests
Assert-NativeSuccess
& $Python scripts/run_safety_challenges.py --output data/output/module_8_safety_guard/challenges/verify_1/safety_challenge_report.json
Assert-NativeSuccess
& $Python scripts/run_safety_challenges.py --output data/output/module_8_safety_guard/challenges/verify_2/safety_challenge_report.json
Assert-NativeSuccess
& $Python scripts/compare_safety_reports.py data/output/module_8_safety_guard/challenges/verify_1/safety_challenge_report.json data/output/module_8_safety_guard/challenges/verify_2/safety_challenge_report.json
Assert-NativeSuccess
& $Python scripts/replay_safety_guard.py --output data/output/module_8_safety_guard/replay/verify_1/safety_replay_report.json
Assert-NativeSuccess
& $Python scripts/replay_safety_guard.py --output data/output/module_8_safety_guard/replay/verify_2/safety_replay_report.json
Assert-NativeSuccess
& $Python scripts/compare_safety_reports.py data/output/module_8_safety_guard/replay/verify_1/safety_replay_report.json data/output/module_8_safety_guard/replay/verify_2/safety_replay_report.json
Assert-NativeSuccess
& $Python scripts/sync_safety_write_attempts.py
Assert-NativeSuccess
& $Python scripts/validate_safety_guard.py
Assert-NativeSuccess
& $Python scripts/compare_safety_runs.py
Assert-NativeSuccess
& $Python scripts/inspect_safety_guard.py --query summary
Assert-NativeSuccess
Write-Output "MODULE 8 VERIFICATION: PASS"
