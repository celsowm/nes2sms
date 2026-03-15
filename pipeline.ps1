param (
    [string]$Rom = "homebrews/pong.nes",
    [string]$OutDir = "out/pong_sms",
    [switch]$Run,
    [switch]$CleanOut
)

$ErrorActionPreference = "Stop"

Write-Host "=== NES2SMS Pipeline ===" -ForegroundColor Cyan

if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "`n=== ERROR ===" -ForegroundColor Red
    Write-Host "Python não encontrado no PATH. Instale/configure Python para usar o pipeline." -ForegroundColor Red
    exit 1
}

$convertArgs = @("-m", "nes2sms.cli.main", "convert", "--nes", $Rom, "--out", $OutDir, "--build")

Write-Host "[config] CLI command: python -m nes2sms.cli.main" -ForegroundColor DarkCyan
Write-Host "[config] Output directory: $OutDir" -ForegroundColor DarkCyan
if ($CleanOut) {
    if (Test-Path $OutDir) {
        Write-Host "[config] Cleaning existing output directory..." -ForegroundColor Yellow
        Remove-Item -Path $OutDir -Recurse -Force
    }
    else {
        Write-Host "[config] Clean requested, but output directory does not exist yet." -ForegroundColor DarkCyan
    }
}

# Step 1: One-step conversion + build (official flow)
Write-Host "`n[1/2] Running one-step convert --build..." -ForegroundColor Cyan
& python @convertArgs
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
        Write-Host "Launching ROM via run_sms.ps1 (with keyboard capture helper)..." -ForegroundColor Cyan
        & (Join-Path $PSScriptRoot "run_sms.ps1") $OutDir
        if ($LASTEXITCODE -ne 0) {
            Write-Host "`n=== ERROR ===" -ForegroundColor Red
            Write-Host "run_sms.ps1 failed with exit code $LASTEXITCODE" -ForegroundColor Red
            exit $LASTEXITCODE
        }
    }
}
else {
    Write-Host "`n=== ERROR ===" -ForegroundColor Red
    Write-Host "ROM was not created. Check build logs above." -ForegroundColor Red
    exit 1
}
