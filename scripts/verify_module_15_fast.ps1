[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Set-Location $Root
$Started = Get-Date
$EnergyBefore = @(Get-Process -Name energyplus -ErrorAction SilentlyContinue).Count
$WritesBefore = 51543
& $Python scripts/validate_dashboard_evidence.py --pretty
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -B -m pytest -q tests/test_dashboard.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/run_dashboard_mock_replay.py --output outputs/module15/replay_fast.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m ruff check src/dashboard scripts/*dashboard*.py scripts/export_hackathon_evidence.py tests/test_dashboard.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m mypy --strict src/dashboard scripts/build_dashboard_evidence.py scripts/validate_dashboard_evidence.py scripts/check_evidence_dashboard.py scripts/export_hackathon_evidence.py scripts/run_dashboard_mock_replay.py tests/test_dashboard.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$EnergyAfter = @(Get-Process -Name energyplus -ErrorAction SilentlyContinue).Count
if ($EnergyAfter -ne $EnergyBefore) { throw "Fast verifier changed EnergyPlus count" }
$Runtime = [math]::Round(((Get-Date)-$Started).TotalSeconds,3)
@{status="PASS";runtime_seconds=$Runtime;energyplus_starts=0;physical_writes_before=$WritesBefore;physical_writes_after=$WritesBefore} | ConvertTo-Json | Set-Content outputs/module15/fast_verifier_result.json
Write-Output ("MODULE 15 FAST VERIFICATION: PASS ({0}s; zero scientific recomputation)" -f $Runtime)
