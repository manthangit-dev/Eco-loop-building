$ErrorActionPreference = "Stop"
$python = "$PSScriptRoot\..\.venv\Scripts\python.exe"
& $python $PSScriptRoot\validate_microtwin.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m mypy
exit $LASTEXITCODE
