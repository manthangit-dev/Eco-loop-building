$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Repository virtual-environment Python is missing: $Python"
}
Set-Location $ProjectRoot

& $Python -B scripts/run_api_baseline.py --config config/api_runner.yaml
if ($LASTEXITCODE -ne 0) { throw "Module 3 API runner failed." }

& $Python -B scripts/validate_baseline.py --config config/baseline.yaml `
    --output-directory data/output/module_3_api_runner/current `
    --allowed-output-root data/output/module_3_api_runner
if ($LASTEXITCODE -ne 0) { throw "Independent Module 3 output validation failed." }

& $Python -B scripts/compare_runner_outputs.py --config config/api_runner.yaml
if ($LASTEXITCODE -ne 0) { throw "Module 2/Module 3 structural comparison failed." }

Write-Host "PASS: Module 3 Runtime API run, validation, and comparison succeeded."

