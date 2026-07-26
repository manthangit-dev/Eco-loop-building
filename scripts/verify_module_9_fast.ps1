$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Started = Get-Date
function Assert-NativeSuccess { if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
Set-Location $Root
& $Python -m pytest -q tests/test_mcp_config.py tests/test_mcp_models.py tests/test_mcp_registry.py tests/test_mcp_pagination.py tests/test_mcp_service.py tests/test_mcp_storage.py
Assert-NativeSuccess
& $Python -m ruff check src/mcp_server src/storage/mcp_schema.py src/storage/mcp_store.py scripts/*mcp*.py tests/test_mcp_*.py
Assert-NativeSuccess
& $Python scripts/replay_mcp_session.py --output data/output/module_9_mcp/replay/fast_1.json
Assert-NativeSuccess
& $Python scripts/replay_mcp_session.py --output data/output/module_9_mcp/replay/fast_2.json
Assert-NativeSuccess
& $Python scripts/compare_mcp_replays.py data/output/module_9_mcp/replay/fast_1.json data/output/module_9_mcp/replay/fast_2.json
Assert-NativeSuccess
& $Python scripts/smoke_mcp_server.py
Assert-NativeSuccess
& $Python scripts/validate_mcp_server.py --replay data/output/module_9_mcp/replay/fast_1.json
Assert-NativeSuccess
$Elapsed = [math]::Round(((Get-Date) - $Started).TotalSeconds, 3)
Write-Output "MODULE 9 FAST VERIFICATION: PASS (${Elapsed}s)"
