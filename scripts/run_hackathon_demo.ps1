[CmdletBinding()]
param([ValidateRange(1024,65535)][int]$Port = 8765, [switch]$NoBrowser)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Set-Location $Root
& $Python scripts/validate_dashboard_evidence.py --pretty
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output "DEMO FLOW: overview -> candidates -> MicroTwin -> Ledger -> Thermal Bank -> approval -> safety -> native/live -> reconciliation -> provenance -> limitations"
Write-Output "LIMITS: annual savings NOT ESTABLISHED; real-building control NOT IMPLEMENTED; electricity increased; interval coverage 41.67%; demand model UNAVAILABLE; RTFU is not energy."
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_evidence_dashboard.ps1 `
    -Port $Port -NoBrowser:$NoBrowser
