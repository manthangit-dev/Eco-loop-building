[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Set-Location $Root
$Started = Get-Date
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify_module_13_fast.ps1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/run_ledger_mock_replay.py --repeat 2 --validate-coverage --require-dedicated --require-mutation-sensitivity --fail-on-placeholder --audit-output outputs/module13/replay_fixture_audit.json --output outputs/module13/final_replay.json --json | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/validate_microtwin.py | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/validate_mcp_server.py | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/validate_ledger_smoke.py | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_ledger_demo.ps1 -SkipTests -Json | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_ledger_demo.ps1 -TryRealModel -SkipTests -Json | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -B -m pytest -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m mypy --strict src scripts tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output ("MODULE 13 FULL VERIFICATION: PASS ({0}s; EnergyPlus and training skipped)" -f [math]::Round(((Get-Date)-$Started).TotalSeconds,3))
