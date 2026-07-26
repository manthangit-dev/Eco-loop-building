[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$InstallRuntime,
    [switch]$InstallModel,
    [string]$Model,
    [switch]$RunSmoke
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
Set-Location $Root
if ($InstallRuntime) {
    Write-Output "Explicit runtime installation requested. Review the winget prompt and package source."
    winget install --id Ollama.Ollama --exact
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$Ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $Ollama) {
    $UserOllama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
    if (Test-Path $UserOllama) {
        $env:Path = (Split-Path -Parent $UserOllama) + ";" + $env:Path
        $Ollama = Get-Command ollama -ErrorAction SilentlyContinue
    }
}
if (-not $Ollama) {
    Write-Output "Ollama is not installed. Default check performs no installation."
    exit 0
}
ollama --version
ollama list
& $Python scripts/discover_local_models.py
if ($InstallModel) {
    if (-not $Model) { Write-Error "-InstallModel requires explicit -Model <name>."; exit 2 }
    $AllowedModels = @("qwen3:4b", "qwen3:1.7b", "qwen3:0.6b")
    if ($Model -notin $AllowedModels -or $Model.EndsWith(":cloud") -or $Model.Contains("/")) {
        Write-Error "Model is not in the reviewed local allowlist: $Model"; exit 2
    }
    Write-Output "Explicit model download requested: $Model. Verify model size/license before continuing."
    ollama pull $Model
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if ($RunSmoke) { & $Python scripts/run_llm_real_smoke.py; exit $LASTEXITCODE }
exit 0
