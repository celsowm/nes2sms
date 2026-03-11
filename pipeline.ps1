param (
    [string]$Rom = "homebrews/pong.nes",
    [string]$OutDir = "out/pong_sms",
    [switch]$Run
)

$ErrorActionPreference = "Stop"

Write-Host "=== NES2SMS Pipeline ===" -ForegroundColor Cyan

# Setup command
$nes2sms = "nes2sms"

# Step 1: One-step conversion + build (official flow)
Write-Host "`n[1/2] Running one-step convert --build..." -ForegroundColor Cyan
$convertArgs = @("convert", "--nes", $Rom, "--out", $OutDir, "--build")
if ($Run) {
    $convertArgs += "--run"
}
& $nes2sms @convertArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n=== ERROR ===" -ForegroundColor Red
    Write-Host "Conversion failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

# Step 2: Validate generated project is not using critical placeholders
Write-Host "`n[2/2] Validating generated assets loader..." -ForegroundColor Cyan
$assetsAsmPath = Join-Path $OutDir "build/assets.asm"
if (!(Test-Path $assetsAsmPath)) {
    Write-Host "`n=== ERROR ===" -ForegroundColor Red
    Write-Host "Generated assets.asm not found: $assetsAsmPath" -ForegroundColor Red
    exit 1
}

$assetsAsm = Get-Content -Path $assetsAsmPath -Raw
$placeholderChecks = @(
    @{ Name = "LoadPalettes"; Pattern = "(?ms)^\s*LoadPalettes:\s*ret\b" },
    @{ Name = "LoadTiles"; Pattern = "(?ms)^\s*LoadTiles:\s*ret\b" }
)

$failedChecks = @()
foreach ($check in $placeholderChecks) {
    if ($assetsAsm -match $check.Pattern) {
        $failedChecks += $check.Name
    }
}

if ($failedChecks.Count -gt 0) {
    Write-Host "`n=== ERROR ===" -ForegroundColor Red
    Write-Host "Critical placeholders detected in generated assets loader: $($failedChecks -join ', ')" -ForegroundColor Red
    Write-Host "Expected non-placeholder implementations to load palettes/tiles into VRAM." -ForegroundColor Yellow
    exit 1
}

# Check if ROM was created
$romPath = "$OutDir/build/game.sms"
if (Test-Path $romPath) {
    Write-Host "`n=== SUCCESS ===" -ForegroundColor Green
    Write-Host "ROM created: $romPath" -ForegroundColor Green
    if ($Run) {
        Write-Host "Emulator launch was requested and handled by 'nes2sms convert --run'." -ForegroundColor Green
    }
}
else {
    Write-Host "`n=== ERROR ===" -ForegroundColor Red
    Write-Host "ROM was not created. Check build logs above." -ForegroundColor Red
    exit 1
}
