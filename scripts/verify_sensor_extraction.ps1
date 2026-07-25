$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Repository virtual-environment Python is missing: $Python"
}
Set-Location $ProjectRoot

& $Python -B scripts/run_sensor_extraction.py --api-config config/api_runner.yaml `
    --sensor-config config/sensors.yaml
if ($LASTEXITCODE -ne 0) { throw "Module 4 sensor extraction failed." }

& $Python -B scripts/validate_sensor_extraction.py --sensor-config config/sensors.yaml
if ($LASTEXITCODE -ne 0) { throw "Independent sensor validation failed." }

& $Python -B scripts/compare_sensor_run_to_baseline.py --api-config config/api_runner.yaml
if ($LASTEXITCODE -ne 0) { throw "Module 3/Module 4 comparison failed." }

Write-Host "PASS: Module 4 extraction, validation, and physical comparison succeeded."

