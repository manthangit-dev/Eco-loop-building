[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Set-Location $Root
$Started = Get-Date
$Before = @(Get-Process -Name energyplus -ErrorAction SilentlyContinue).Count
& $Python scripts/preflight_module_14.py | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/validate_execution.py | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -B -m pytest -q tests/test_execution.py tests/test_mcp_registry.py tests/test_runtime_cli.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/run_execution_mock_replay.py --repeat 1 --output outputs/module14/execution_replay_fast.json | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m ruff check src/execution src/storage/execution_schema.py src/storage/execution_store.py src/agent/execution_policy.py scripts/*execution*.py tests/test_execution.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m mypy --strict src/execution src/storage/execution_schema.py src/storage/execution_store.py src/agent/execution_policy.py scripts/preflight_module_14.py scripts/create_execution_approval.py scripts/validate_execution_approval.py scripts/run_execution_replay_dry_run.py scripts/run_execution_short.py scripts/run_execution_mock_replay.py tests/test_execution.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$After = @(Get-Process -Name energyplus -ErrorAction SilentlyContinue).Count
if ($After -ne $Before) { throw "Fast verifier changed EnergyPlus process count" }
Write-Output ("MODULE 14 FAST VERIFICATION: PASS ({0}s; zero EnergyPlus starts)" -f [math]::Round(((Get-Date)-$Started).TotalSeconds,3))

