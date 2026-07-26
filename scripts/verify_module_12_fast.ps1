$ErrorActionPreference = "Stop"
$python = "$PSScriptRoot\..\.venv\Scripts\python.exe"
& $python $PSScriptRoot\validate_microtwin.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m pytest tests/test_microtwin.py tests/test_mcp_registry.py -q
exit $LASTEXITCODE
