$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Started = Get-Date
function Assert-NativeSuccess { if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
Set-Location $Root
& $Python -m pytest -q tests/test_runtime_cli.py tests/test_mcp_service.py tests/test_agent_supervisor.py
Assert-NativeSuccess
& $Python -m ruff check scripts/demo_common.py scripts/select_demo_run.py scripts/prepare_demo_requests.py scripts/list_mcp_tools.py scripts/call_mcp_tool.py scripts/run_demo_control_proposal.py scripts/run_mcp_server_smoke.py tests/test_runtime_cli.py
Assert-NativeSuccess
& $Python scripts/run_mcp_server_smoke.py
Assert-NativeSuccess
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/run_current_demo.ps1
Assert-NativeSuccess
$EnergyPlus = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^energyplus$' }).Count
if ($EnergyPlus -ne 0) { Write-Error "Unexpected EnergyPlus process"; exit 4 }
$Elapsed = [math]::Round(((Get-Date) - $Started).TotalSeconds, 3)
Write-Output "MODULE 10A FAST VERIFICATION: PASS (${Elapsed}s)"
