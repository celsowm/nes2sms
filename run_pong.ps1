$ProjectName = "pong_sms"
$emulatorPath = "$PSScriptRoot\emulators\blastem\blastem.exe"
$romPath = "$PSScriptRoot\out\$ProjectName\build\game.sms"

Write-Host "=== Running $ProjectName ===" -ForegroundColor Cyan

if (Test-Path $emulatorPath) {
    if (Test-Path $romPath) {
        Write-Host "Launching BlastEm with $romPath..." -ForegroundColor Green
        Start-Process $emulatorPath -ArgumentList "`"$romPath`""
    }
    else {
        Write-Host "ERROR: ROM not found at $romPath" -ForegroundColor Red
        Write-Host "Please run '.\build_sms.ps1' first to compile the game." -ForegroundColor Yellow
    }
}
else {
    Write-Host "ERROR: Emulator not found at $emulatorPath" -ForegroundColor Red
    Write-Host "Please run '.\download_emulator.ps1' first." -ForegroundColor Yellow
}
