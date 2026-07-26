$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Started = Get-Date
Set-Location $Root
& $Python -m pytest tests/test_trusted_field_boundary.py tests/test_planning.py tests/test_mcp_registry.py -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/validate_planning.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python scripts/run_planning_mock_replay.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m ruff check src/planning src/agent src/mcp_server src/storage scripts tests/test_planning.py tests/test_trusted_field_boundary.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python -m mypy --strict src/planning src/agent src/mcp_server src/storage scripts
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output ("MODULE 11 FAST VERIFICATION: PASS ({0}s)" -f [math]::Round(((Get-Date)-$Started).TotalSeconds,3))
