[CmdletBinding()]
param(
    [switch]$NoClean
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Repository Python is missing: $Python"
}

function Get-DotEnvValue {
    param([string]$Path, [string]$Name)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $Match = Select-String -LiteralPath $Path -Pattern ("^\s*" + [regex]::Escape($Name) + "\s*=") |
        Select-Object -Last 1
    if (-not $Match) { return $null }
    return (($Match.Line -split "=", 2)[1]).Trim().Trim('"').Trim("'")
}

function Assert-ChildPath {
    param([string]$Path, [string]$AllowedRoot)
    $ResolvedPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $ResolvedRoot = [System.IO.Path]::GetFullPath($AllowedRoot).TrimEnd('\')
    if (-not $ResolvedPath.StartsWith($ResolvedRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe output path outside dedicated Module 2 root: $ResolvedPath"
    }
}

function Get-InstallationOutputs {
    param([string[]]$Directories)
    $Extensions = @(".csv", ".eio", ".end", ".err", ".eso", ".htm", ".html", ".mdd",
        ".mtd", ".mtr", ".rdd", ".rvaudit", ".sql")
    $Files = foreach ($Directory in $Directories) {
        if (Test-Path -LiteralPath $Directory -PathType Container) {
            Get-ChildItem -LiteralPath $Directory -File |
                Where-Object {
                    $Extensions -contains $_.Extension.ToLowerInvariant() -or
                    $_.Name.ToLowerInvariant().StartsWith("eplusout.")
                } |
                ForEach-Object { $_.FullName }
        }
    }
    return @($Files | Sort-Object -Unique)
}

function Move-PreviousRun {
    param([string]$Directory, [string]$AllowedRoot, [switch]$Keep)
    Assert-ChildPath -Path $Directory -AllowedRoot $AllowedRoot
    if (-not (Test-Path -LiteralPath $Directory)) { return }
    if ($Keep) {
        throw "-NoClean requires an absent output directory: $Directory"
    }
    $ArchiveRoot = Join-Path $AllowedRoot "archive"
    New-Item -ItemType Directory -Force -Path $ArchiveRoot | Out-Null
    $Stamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
    $Archive = Join-Path $ArchiveRoot ("{0}_{1}" -f (Split-Path $Directory -Leaf), $Stamp)
    Move-Item -LiteralPath $Directory -Destination $Archive
    Write-Host "Archived previous run to: $Archive"
}

function Invoke-EnergyPlusRun {
    param(
        [string]$Executable,
        [string]$OutputDirectory,
        [string]$Prefix,
        [string]$Weather,
        [string]$Idf,
        [int]$TimeoutSeconds
    )
    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
    $Stdout = Join-Path $OutputDirectory "energyplus_stdout.log"
    $Stderr = Join-Path $OutputDirectory "energyplus_stderr.log"
    $Arguments = @(
        "-d", ('"{0}"' -f $OutputDirectory),
        "-p", $Prefix,
        "-s", "C",
        "-w", ('"{0}"' -f $Weather),
        "-r",
        ('"{0}"' -f $Idf)
    )
    $Process = Start-Process -FilePath $Executable -ArgumentList $Arguments -PassThru `
        -NoNewWindow -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
    if (-not $Process.WaitForExit($TimeoutSeconds * 1000)) {
        $Process.Kill()
        throw "EnergyPlus exceeded the configured timeout of $TimeoutSeconds seconds."
    }
    $Process.WaitForExit()
    return [int]$Process.ExitCode
}

function Get-ErrorCounts {
    param([string]$ErrorFile)
    if (-not (Test-Path -LiteralPath $ErrorFile -PathType Leaf)) {
        throw "EnergyPlus did not create an error report: $ErrorFile"
    }
    $Text = Get-Content -Raw -LiteralPath $ErrorFile
    $Matches = [regex]::Matches(
        $Text,
        "(\d+)\s+Warning(?:s)?;\s*(\d+)\s+Severe Errors?",
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )
    if ($Matches.Count -eq 0) {
        throw "Could not parse the final EnergyPlus error summary: $ErrorFile"
    }
    $Final = $Matches[$Matches.Count - 1]
    $Fatal = ([regex]::Matches(
        $Text,
        "^\s*\*\*\s*Fatal\s*\*\*",
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor
            [System.Text.RegularExpressions.RegexOptions]::Multiline
    )).Count
    if ($Text.Contains("Fatal Error Detected") -and $Fatal -eq 0) { $Fatal = 1 }
    return @{
        warnings = [int]$Final.Groups[1].Value
        severe = [int]$Final.Groups[2].Value
        fatal = $Fatal
    }
}

$ConfigPath = Join-Path $ProjectRoot "config\baseline.yaml"
$ConfigText = & $Python -B -c @"
import json, pathlib, yaml
print(json.dumps(yaml.safe_load(pathlib.Path(r'$ConfigPath').read_text(encoding='utf-8'))))
"@
if ($LASTEXITCODE -ne 0) { throw "Could not load baseline configuration." }
$Config = $ConfigText | ConvertFrom-Json

$EnvFile = Join-Path $ProjectRoot ".env"
$EnergyPlusHome = $env:ENERGYPLUS_HOME
if ([string]::IsNullOrWhiteSpace($EnergyPlusHome)) {
    $EnergyPlusHome = Get-DotEnvValue -Path $EnvFile -Name "ENERGYPLUS_HOME"
}
if ([string]::IsNullOrWhiteSpace($EnergyPlusHome)) {
    throw "ENERGYPLUS_HOME is not configured in the process or .env."
}
$EnergyPlusHome = [System.IO.Path]::GetFullPath($EnergyPlusHome)
$EnergyPlusExe = Join-Path $EnergyPlusHome "energyplus.exe"
if (-not (Test-Path -LiteralPath $EnergyPlusExe -PathType Leaf)) {
    throw "EnergyPlus executable is missing: $EnergyPlusExe"
}
$Version = (& $EnergyPlusExe --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $Version -notmatch "26\.1") {
    throw "EnergyPlus 26.1 is required; reported: $Version"
}

$SourceIdf = Join-Path $ProjectRoot $Config.baseline.source_model
$BaselineIdf = Join-Path $ProjectRoot $Config.baseline.baseline_model
$WeatherFilename = [string]$Config.baseline.weather_filename
$WeatherCandidates = @(
    (Join-Path $ProjectRoot ("weather\input\" + $WeatherFilename))
)
$ConfiguredWeather = Get-DotEnvValue -Path $EnvFile -Name "ENERGYPLUS_WEATHER_PATH"
if (-not [string]::IsNullOrWhiteSpace($env:ENERGYPLUS_WEATHER_PATH)) {
    $ConfiguredWeather = $env:ENERGYPLUS_WEATHER_PATH
}
if (-not [string]::IsNullOrWhiteSpace($ConfiguredWeather)) {
    $WeatherCandidates += $ConfiguredWeather
}
$WeatherCandidates += Join-Path $EnergyPlusHome ("WeatherData\" + $WeatherFilename)
$Weather = $WeatherCandidates |
    Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    Select-Object -First 1
if (-not $Weather) { throw "Chicago O'Hare weather file was not found." }

$ModuleOutputRoot = Join-Path $ProjectRoot "data\output\module_2_baseline"
$SmokeOutput = Join-Path $ModuleOutputRoot "smoke"
$FinalOutput = Join-Path $ProjectRoot $Config.baseline.output_directory
Assert-ChildPath -Path $SmokeOutput -AllowedRoot $ModuleOutputRoot
Assert-ChildPath -Path $FinalOutput -AllowedRoot $ModuleOutputRoot
New-Item -ItemType Directory -Force -Path $ModuleOutputRoot | Out-Null
Move-PreviousRun -Directory $SmokeOutput -AllowedRoot $ModuleOutputRoot -Keep:$NoClean
Move-PreviousRun -Directory $FinalOutput -AllowedRoot $ModuleOutputRoot -Keep:$NoClean

$InstallWatch = @($EnergyPlusHome, (Join-Path $EnergyPlusHome "ExampleFiles"))
$Before = Get-InstallationOutputs -Directories $InstallWatch
$Timeout = [int]$Config.execution.timeout_seconds

Write-Host "Stage 1: preserved source-model smoke run"
$SmokeStart = (Get-Date).ToUniversalTime().ToString("o")
$SmokeExit = Invoke-EnergyPlusRun -Executable $EnergyPlusExe -OutputDirectory $SmokeOutput `
    -Prefix "smoke" -Weather $Weather -Idf $SourceIdf -TimeoutSeconds $Timeout
$SmokeCounts = Get-ErrorCounts -ErrorFile (Join-Path $SmokeOutput "smoke.err")
@{
    started_at_utc = $SmokeStart
    completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    energyplus_exit_code = $SmokeExit
    warning_count = $SmokeCounts.warnings
    severe_count = $SmokeCounts.severe
    fatal_count = $SmokeCounts.fatal
    model = "models/source/5ZoneAirCooled_v26_1_original.idf"
    weather_filename = $WeatherFilename
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $SmokeOutput "smoke_metadata.json") `
    -Encoding UTF8
if ($SmokeExit -ne 0 -or $SmokeCounts.severe -ne 0 -or $SmokeCounts.fatal -ne 0) {
    throw "Source smoke run failed: exit=$SmokeExit severe=$($SmokeCounts.severe) fatal=$($SmokeCounts.fatal)"
}

Write-Host "Stage 2: reporting-only derived baseline run"
$FinalStart = (Get-Date).ToUniversalTime().ToString("o")
$FinalExit = Invoke-EnergyPlusRun -Executable $EnergyPlusExe -OutputDirectory $FinalOutput `
    -Prefix ([string]$Config.baseline.output_prefix) -Weather $Weather -Idf $BaselineIdf `
    -TimeoutSeconds $Timeout
$After = Get-InstallationOutputs -Directories $InstallWatch
@{
    started_at_utc = $FinalStart
    completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    energyplus_version = $Version
    energyplus_exit_code = $FinalExit
    model = [string]$Config.baseline.baseline_model
    weather_filename = $WeatherFilename
    output_prefix = [string]$Config.baseline.output_prefix
    command_flags = @("-d", "-p", "-s C", "-w", "-r")
    installation_generated_files_before = @($Before)
    installation_generated_files_after = @($After)
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $FinalOutput "run_metadata.json") `
    -Encoding UTF8
if ($FinalExit -ne 0) { throw "EnergyPlus baseline run failed with exit code $FinalExit." }

& $Python -B (Join-Path $PSScriptRoot "validate_baseline.py") --config $ConfigPath
if ($LASTEXITCODE -ne 0) { throw "Baseline validation failed with exit code $LASTEXITCODE." }
Write-Host "PASS: Module 2 source smoke run and derived baseline run validated."
Write-Host "Final output directory: $FinalOutput"

