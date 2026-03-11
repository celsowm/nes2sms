param (
    [string]$Rom = "homebrews/pong.nes",
    [string]$OutDir = "out/pong_sms",
    [switch]$Run
)

$ErrorActionPreference = "Stop"

Write-Host "=== NES2SMS Pipeline ===" -ForegroundColor Cyan

# Setup command
$nes2sms = "nes2sms"

# Step 1: Ingest
Write-Host "`n[1/6] Ingesting ROM: $Rom" -ForegroundColor Cyan
& $nes2sms ingest --nes $Rom --out $OutDir

# Step 2: Analyze Mapper
Write-Host "`n[2/6] Analyzing mapper..." -ForegroundColor Cyan
& $nes2sms analyze-mapper --manifest "$OutDir/work/manifest_sms.json" --out "$OutDir/work"

# Step 3: Convert Graphics
Write-Host "`n[3/6] Converting graphics..." -ForegroundColor Cyan
& $nes2sms convert-gfx `
    --chr "$OutDir/work/chr.bin" `
    --prg "$OutDir/work/prg.bin" `
    --out "$OutDir/assets"

# Step 4: Convert Audio
Write-Host "`n[4/6] Converting audio..." -ForegroundColor Cyan
& $nes2sms convert-audio `
    --prg "$OutDir/work/prg.bin" `
    --out "$OutDir/assets/audio"

# Step 5: Generate Project
Write-Host "`n[5/6] Generating WLA-DX project..." -ForegroundColor Cyan
& $nes2sms generate `
    --manifest "$OutDir/work/manifest_sms.json" `
    --assets "$OutDir/assets" `
    --out "$OutDir/build"

# Step 6: Build
Write-Host "`n[6/6] Building ROM..." -ForegroundColor Cyan
& $nes2sms build --dir "$OutDir/build"

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
