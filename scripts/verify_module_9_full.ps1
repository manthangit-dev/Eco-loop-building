$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Started = Get-Date
function Assert-NativeSuccess { if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
Set-Location $Root
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
& $Python scripts/validate_baseline.py --config config/baseline.yaml
Assert-NativeSuccess
& $Python scripts/replay_mcp_session.py --output data/output/module_9_mcp/replay/verify_1.json
Assert-NativeSuccess
& $Python scripts/replay_mcp_session.py --output data/output/module_9_mcp/replay/verify_2.json
Assert-NativeSuccess
& $Python scripts/compare_mcp_replays.py data/output/module_9_mcp/replay/verify_1.json data/output/module_9_mcp/replay/verify_2.json
Assert-NativeSuccess
& $Python scripts/smoke_mcp_server.py
Assert-NativeSuccess
& $Python scripts/validate_mcp_server.py
Assert-NativeSuccess
$Elapsed = [math]::Round(((Get-Date) - $Started).TotalSeconds, 3)
Write-Output "MODULE 9 FULL VERIFICATION: PASS (${Elapsed}s)"
