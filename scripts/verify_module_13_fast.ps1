[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Set-Location $Root
$Started = Get-Date
$Processes = @(Get-Process -Name energyplus -ErrorAction SilentlyContinue).Count
& $Python scripts/preflight_module_13.py --energyplus-process-count $Processes | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/validate_ledger.py | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m pytest tests/test_ledger.py tests/test_ledger_replay_fixtures.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/run_ledger_mock_replay.py --validate-coverage --require-dedicated --require-mutation-sensitivity --fail-on-placeholder --audit-output outputs/module13/replay_fixture_audit.json --output outputs/module13/fast_replay.json --json | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/validate_ledger_smoke.py | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m ruff check src/ledger src/thermal_bank src/storage/ledger_schema.py src/storage/ledger_store.py src/agent/ledger_policy.py scripts/run_ledger_mock_replay.py tests/test_ledger.py tests/test_ledger_replay_fixtures.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m mypy --strict src/ledger src/thermal_bank src/storage/ledger_schema.py src/storage/ledger_store.py src/agent/ledger_policy.py scripts/run_ledger_mock_replay.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output ("MODULE 13 FAST VERIFICATION: PASS ({0}s; zero EnergyPlus starts)" -f [math]::Round(((Get-Date)-$Started).TotalSeconds,3))
