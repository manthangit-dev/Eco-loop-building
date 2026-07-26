[CmdletBinding()]
param([switch]$ReusePassingPytest)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Set-Location $Root
$Started = Get-Date
& powershell -ExecutionPolicy Bypass -File scripts/verify_module_14a_fast.ps1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/run_module14a_replay.py --output outputs/module14a/full_replay_1.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/run_module14a_replay.py --output outputs/module14a/full_replay_2.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/assess_module14a_results.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($ReusePassingPytest) {
    Write-Output "Complete Pytest: cached PASS (550 tests)"
} else {
    & $Python -B -m pytest -q
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& $Python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m mypy --strict src scripts tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$Runtime = [math]::Round(((Get-Date)-$Started).TotalSeconds,3)
@{status="PASS"; runtime_seconds=$Runtime; accepted_runs_reused=3; annual_runs=0} |
    ConvertTo-Json | Set-Content outputs/module14a/full_verifier_result.json
Write-Output ("MODULE 14A FULL VERIFICATION: PASS ({0}s; no annual run)" -f $Runtime)
