# PowerShell 7 / Windows PowerShell 5.1; launch from ANY directory.
param(
    [Parameter(Mandatory=$true)][string]$GodotExe,
    [switch]$Headless,
    [string]$PythonExe = "python"
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$project = Join-Path $repo "godot_render"
$outputDir = Join-Path $repo "data\renders\bs-m4b"
$output = Join-Path $outputDir "m4b-proof.avi"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$version = (& $GodotExe --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $version -notmatch "4\.7\.2") {
    throw "Godot 4.7.2 required. Executable reports: $version"
}
Write-Host "Using Godot: $version"
if (Test-Path $output) { Remove-Item $output -Force }

$godotArgs = @("--path", $project, "--write-movie", $output, "--fixed-fps", "30", "--quit-after", "150")
if ($Headless) {
    # Not the default! Headless builds may use dummy rendering and produce blank frames.
    Write-Warning "Headless Movie Maker can be unsupported or blank. Windowed render is the baseline."
    $godotArgs = @("--headless") + $args
}
& $GodotExe @godotArgs
if ($LASTEXITCODE -ne 0) { throw "Godot exited with code $LASTEXITCODE" }

& $PythonExe (Join-Path $PSScriptRoot "verify_m4b_proof.py") $output
if ($LASTEXITCODE -ne 0) { throw "Video verification failed" }
Write-Host "M4-B PROOF PASSED: $output"
