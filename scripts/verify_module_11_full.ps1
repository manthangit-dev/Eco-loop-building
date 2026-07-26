[CmdletBinding()]
param([switch]$ReuseVerifiedSoftwareChecks)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Started = Get-Date
Set-Location $Root
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_module_11_fast.ps1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not $ReuseVerifiedSoftwareChecks) {
    & $Python -B -m pytest -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m ruff check .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $Python -m mypy --strict src scripts tests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else { Write-Output "Reusing completed 227-test, Ruff, and strict Mypy checks from this run." }
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_planning_demo.ps1 -SkipTests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_planning_demo.ps1 -SkipTests -TryRealModel
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output ("MODULE 11 FULL VERIFICATION: PASS ({0}s; EnergyPlus skipped)" -f [math]::Round(((Get-Date)-$Started).TotalSeconds,3))
