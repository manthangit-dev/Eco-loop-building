$ErrorActionPreference = "Stop"
& $PSScriptRoot\..\.venv\Scripts\python.exe $PSScriptRoot\run_microtwin_demo.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
