[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Set-Location $Root
$Started = Get-Date
$Before = @(Get-Process -Name energyplus -ErrorAction SilentlyContinue).Count
& $Python scripts/prepare_module14a_runtime.py | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/build_module14a_package.py | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/control_effect_preflight.py | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -B -m pytest -q tests/test_module14a_alignment.py tests/test_execution.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/run_module14a_replay.py --output outputs/module14a/replay_fast.json | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m ruff check src/execution scripts/*module14a*.py tests/test_module14a_alignment.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m mypy --strict src/execution scripts/run_module14a_replay.py tests/test_module14a_alignment.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$After = @(Get-Process -Name energyplus -ErrorAction SilentlyContinue).Count
if ($After -ne $Before) { throw "Fast verifier changed EnergyPlus process count" }
$Runtime = [math]::Round(((Get-Date)-$Started).TotalSeconds,3)
@{status="PASS"; runtime_seconds=$Runtime; energyplus_starts=0} |
    ConvertTo-Json | Set-Content outputs/module14a/fast_verifier_result.json
Write-Output ("MODULE 14A FAST VERIFICATION: PASS ({0}s; zero EnergyPlus starts)" -f $Runtime)
