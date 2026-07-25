$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

& py -3.12 --version
if ($LASTEXITCODE -ne 0) { throw "Python 3.12 is required and was not available through py -3.12." }

if (-not (Test-Path -LiteralPath ".venv")) {
    & py -3.12 -m venv .venv
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip setuptools wheel
& $Python -m pip install -r requirements-dev.txt

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
    Write-Host "Created .env from .env.example; review ENERGYPLUS_HOME."
}

Write-Host "Activate later with: .\.venv\Scripts\Activate.ps1"
& $Python scripts/check_environment.py

