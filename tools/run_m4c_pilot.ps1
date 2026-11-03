# Windowed Godot 4.7.2 Movie Maker launch for the 83-second Pilot 1 previs.
param(
    [Parameter(Mandatory = $true)][string]$GodotExe,
    [switch]$AllowProxy,
    [switch]$SkipCompile,
    [string]$ManifestPath = "",
    [string]$PythonExe = "",
    [ValidateSet("ogv", "avi")][string]$Container = "ogv",
    [switch]$AssembleAudio
)
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$project = Join-Path $repo "godot_render"
if (-not $PythonExe) {
    $venv = Join-Path $repo ".venv\Scripts\python.exe"
    if (Test-Path $venv) { $PythonExe = $venv } else { $PythonExe = "python" }
}

$version = (& $GodotExe --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $version -notmatch "4\.7\.2") {
    throw "Godot 4.7.2 required. Executable reports: $version"
}
Write-Host "Using Godot: $version"

if (-not $SkipCompile) {
    $builder = Join-Path $PSScriptRoot "build_m4c_manifest.py"
    $builderArgs = @($builder, "--project-id", "blueprint-pilot-01", "--quality", "previs")
    if ($AllowProxy) { $builderArgs += "--allow-proxy" }
    $compiled = & $PythonExe @builderArgs
    if ($LASTEXITCODE -ne 0) { throw "Manifest compile failed" }
    $compiled | ForEach-Object { Write-Host $_ }
    $marker = @($compiled) | Where-Object { $_ -like "M4C_MANIFEST=*" } | Select-Object -Last 1
    if (-not $marker) { throw "Compiler did not report a manifest path" }
    $ManifestPath = $marker.Substring("M4C_MANIFEST=".Length)
}
if (-not $ManifestPath -or -not (Test-Path $ManifestPath)) {
    throw "Manifest path is missing: $ManifestPath"
}

$jobDir = Split-Path -Parent $ManifestPath
$output = Join-Path $jobDir ("pilot-previs." + $Container)
if (Test-Path $output) { Remove-Item $output -Force }
& $GodotExe --path $project --scene "res://scenes/DirectorPilot.tscn" --write-movie $output --fixed-fps 30 --quit-after 2490 -- --manifest $ManifestPath
if ($LASTEXITCODE -ne 0) { throw "Godot exited with code $LASTEXITCODE" }

& $PythonExe (Join-Path $PSScriptRoot "verify_m4c_video.py") $output
if ($LASTEXITCODE -ne 0) { throw "Video verification failed" }
Write-Host "M4-C PREVIS PASSED: $output"
if ($AssembleAudio) {
    if ($Container -ne "ogv") { throw "Audio assembly reads pilot-previs.ogv. Re-run without -Container avi." }
    & $PythonExe (Join-Path $PSScriptRoot "assemble_m4d.py") --manifest $ManifestPath
    if ($LASTEXITCODE -ne 0) { throw "Audio assembly failed" }
}
