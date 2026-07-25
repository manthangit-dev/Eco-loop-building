$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) { throw "Repository-local Python is missing: $python" }

& $python (Join-Path $root "scripts\check_environment.py")
if ($LASTEXITCODE -ne 0) { throw "Environment verification failed." }
& $python (Join-Path $root "scripts\validate_baseline.py") --config (Join-Path $root "config\baseline.yaml")
if ($LASTEXITCODE -ne 0) { throw "Module 2 validation failed." }
& (Join-Path $root "scripts\verify_api_runner.ps1")
if ($LASTEXITCODE -ne 0) { throw "Module 3 verification failed." }
& $python (Join-Path $root "scripts\validate_sensor_extraction.py") --sensor-config (Join-Path $root "config\sensors.yaml")
if ($LASTEXITCODE -ne 0) { throw "Module 4 validation failed." }
& $python (Join-Path $root "scripts\discover_actuators.py")
if ($LASTEXITCODE -ne 0) { throw "Actuator discovery failed." }
& $python (Join-Path $root "scripts\run_actuator_test.py") --run-type control --quiet
if ($LASTEXITCODE -ne 0) { throw "Control run failed." }
& $python (Join-Path $root "scripts\validate_actuator_test.py") --run-type control
if ($LASTEXITCODE -ne 0) { throw "Control validation failed." }
& $python (Join-Path $root "scripts\run_actuator_test.py") --run-type intervention --quiet
if ($LASTEXITCODE -ne 0) { throw "Intervention run failed." }
& $python (Join-Path $root "scripts\validate_actuator_test.py")
if ($LASTEXITCODE -ne 0) { throw "Module 5 validation failed." }
& $python (Join-Path $root "scripts\compare_actuator_runs.py")
if ($LASTEXITCODE -ne 0) { throw "Actuator comparison failed." }
Write-Host "PASS: Module 5 safe runtime actuator injection verified."
