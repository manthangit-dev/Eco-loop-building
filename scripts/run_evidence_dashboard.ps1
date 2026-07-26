[CmdletBinding()]
param(
    [ValidateRange(1024,65535)][int]$Port = 8765,
    [switch]$NoBrowser,
    [switch]$RebuildEvidence,
    [switch]$Json,
    [switch]$VerboseOutput,
    [switch]$KeepLogs
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Repository-local Python is missing." }
Set-Location $Root
if ($RebuildEvidence) {
    & $Python scripts/build_dashboard_evidence.py --force --json
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& $Python scripts/validate_dashboard_evidence.py --pretty
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$Url = "http://127.0.0.1:$Port"
Write-Output "SIMULATION-ONLY | READ-ONLY | LOOPBACK-ONLY"
Write-Output "Dashboard URL: $Url"
Write-Output "Evidence snapshot: CURRENT"
if (-not $NoBrowser) { Start-Process $Url }
& $Python -m src.dashboard.server --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
