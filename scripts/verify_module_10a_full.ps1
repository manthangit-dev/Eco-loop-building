$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Started = Get-Date
function Assert-NativeSuccess { if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
Set-Location $Root
& $Python -B -m pytest -p no:cacheprovider
Assert-NativeSuccess
& $Python -m ruff check . --no-cache
Assert-NativeSuccess
& $Python -m mypy --no-incremental src scripts tests
Assert-NativeSuccess
& $Python scripts/validate_baseline.py --config config/baseline.yaml
Assert-NativeSuccess
& $Python scripts/validate_llm_supervisor.py
Assert-NativeSuccess
& $Python scripts/run_llm_mock_replay.py --output data/output/module_10_llm/mock/module10a_full.json
Assert-NativeSuccess
& $Python scripts/run_mcp_server_smoke.py
Assert-NativeSuccess
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run_current_demo.ps1
Assert-NativeSuccess
$EnergyPlus = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^energyplus$' }).Count
if ($EnergyPlus -ne 0) { Write-Error "Unexpected EnergyPlus process"; exit 4 }
$Elapsed = [math]::Round(((Get-Date) - $Started).TotalSeconds, 3)
Write-Output "MODULE 10A FULL VERIFICATION: PASS (${Elapsed}s; annual EnergyPlus skipped)"
