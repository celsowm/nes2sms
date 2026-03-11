param (
    [string]$Rom = "homebrews/pong.nes",
    [string]$OutDir = "out/pong_sms",
    [switch]$Run
)

$ErrorActionPreference = "Stop"

Write-Host "=== NES2SMS Pipeline ===" -ForegroundColor Cyan

# Setup paths
$nes2smsScript = "$PSScriptRoot\nes2sms.py"
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (!$python) {
    $python = (Get-Command python3 -ErrorAction SilentlyContinue).Source
}

if (!$python) {
    Write-Host "ERROR: Python not found. Please install Python 3.10+." -ForegroundColor Red
    exit 1
}

# Step 1: Ingest
Write-Host "`n[1/6] Ingesting ROM: $Rom" -ForegroundColor Cyan
& $python $nes2smsScript ingest --nes $Rom --out $OutDir

# Step 2: Analyze Mapper
Write-Host "`n[2/6] Analyzing mapper..." -ForegroundColor Cyan
& $python $nes2smsScript analyze-mapper --manifest "$OutDir/work/manifest_sms.json" --out "$OutDir/work"

# Step 3: Convert Graphics
Write-Host "`n[3/6] Converting graphics..." -ForegroundColor Cyan
& $python $nes2smsScript convert-gfx `
    --chr "$OutDir/work/chr.bin" `
    --prg "$OutDir/work/prg.bin" `
    --out "$OutDir/assets"

# Step 4: Convert Audio
Write-Host "`n[4/6] Converting audio..." -ForegroundColor Cyan
& $python $nes2smsScript convert-audio `
    --prg "$OutDir/work/prg.bin" `
    --out "$OutDir/assets/audio"

# Step 5: Generate Project
Write-Host "`n[5/6] Generating WLA-DX project..." -ForegroundColor Cyan
& $python $nes2smsScript generate `
    --manifest "$OutDir/work/manifest_sms.json" `
    --assets "$OutDir/assets" `
    --out "$OutDir/build"

# Step 6: Build
Write-Host "`n[6/6] Building ROM..." -ForegroundColor Cyan
& $python $nes2smsScript build --dir "$OutDir/build"

# Check if ROM was created
$romPath = "$OutDir/build/game.sms"
if (Test-Path $romPath) {
    Write-Host "`n=== SUCCESS ===" -ForegroundColor Green
    Write-Host "ROM created: $romPath" -ForegroundColor Green
    
    if ($Run) {
        $emulatorPath = "$PSScriptRoot\emulators\blastem\blastem.exe"
        if (Test-Path $emulatorPath) {
            Write-Host "`nLaunching BlastEm..." -ForegroundColor Cyan
            Start-Process $emulatorPath -ArgumentList "`"$romPath`""
        }
        else {
            Write-Host "`nEmulator not found. Run .\download_emulator.ps1 first." -ForegroundColor Yellow
        }
    }
}
else {
    Write-Host "`n=== ERROR ===" -ForegroundColor Red
    Write-Host "ROM was not created. Check build logs above." -ForegroundColor Red
    exit 1
}
