param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$NesRom,
    [string]$OutPng,
    [string]$OutReport,
    [int]$Frame = 120,
    [int]$TimeoutSeconds = 30,
    [string]$EmulatorPath
)

$ErrorActionPreference = "Stop"

$baseDir = $PSScriptRoot
$resolvedRom = if ([System.IO.Path]::IsPathRooted($NesRom)) {
    (Resolve-Path -Path $NesRom).Path
} else {
    (Resolve-Path -Path (Join-Path -Path $baseDir -ChildPath $NesRom)).Path
}

if (-not $OutPng) {
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($resolvedRom)
    $OutPng = Join-Path -Path $baseDir -ChildPath ("tmp\{0}_nes_raw_reference.png" -f $stem)
}

$outPath = [System.IO.Path]::GetFullPath($OutPng)
$outDir = Split-Path -Path $outPath -Parent
$runtimeDir = Join-Path -Path $outDir -ChildPath "nes_raw_runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

if (-not $OutReport) {
    $OutReport = Join-Path -Path $outDir -ChildPath "raw_reference_report.json"
}
$reportPath = [System.IO.Path]::GetFullPath($OutReport)

$python = @"
from pathlib import Path
from nes2sms.infrastructure.nes_raw_reference_capture import (
    NesRawReferenceCaptureConfig,
    capture_raw_reference_frame,
)

rom_path = Path(r'''$resolvedRom''')
runtime_dir = Path(r'''$runtimeDir''')
png_path = Path(r'''$outPath''')
report_path = Path(r'''$reportPath''')
emulator_path = r'''$EmulatorPath''' or None

captured_png, captured_report = capture_raw_reference_frame(
    NesRawReferenceCaptureConfig(
        nes_path=rom_path,
        output_dir=runtime_dir,
        capture_frame=$Frame,
        timeout_seconds=$TimeoutSeconds,
        emulator_path=emulator_path,
    )
)
png_path.parent.mkdir(parents=True, exist_ok=True)
png_path.write_bytes(captured_png.read_bytes())
report_path.write_text(captured_report.read_text(encoding='utf-8'), encoding='utf-8')
print(png_path)
"@

$existingPythonPath = ""
if ($env:PYTHONPATH) {
    $existingPythonPath = $env:PYTHONPATH
}
$env:PYTHONPATH = (Join-Path -Path $baseDir -ChildPath "src") + [System.IO.Path]::PathSeparator + $existingPythonPath
$result = $python | python -
Write-Host "NES raw reference captured: $result" -ForegroundColor Green
