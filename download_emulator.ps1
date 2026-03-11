$ErrorActionPreference = "Stop"

$emulatorDir = "$PSScriptRoot\emulators"
$blastemDir = "$emulatorDir\blastem"
$zipPath = "$emulatorDir\blastem.zip"
$blastemUrl = "https://www.retrodev.com/blastem/blastem-win32-0.6.2.zip"

Write-Host "=== Master System Emulator Setup (BlastEm) ===" -ForegroundColor Cyan

if (!(Test-Path $emulatorDir)) {
    New-Item -ItemType Directory -Path $emulatorDir | Out-Null
    Write-Host "Created emulators/ directory." -ForegroundColor Green
}

if (!(Test-Path "$blastemDir\blastem.exe")) {
    Write-Host "Baixando BlastEm v0.6.2..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $blastemUrl -OutFile $zipPath
    
    Write-Host "Extraindo BlastEm..." -ForegroundColor Yellow
    if (Test-Path $blastemDir) {
        Remove-Item -Path $blastemDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $blastemDir | Out-Null
    Expand-Archive -Path $zipPath -DestinationPath $blastemDir -Force
    
    # BlastEm zip usually contains everything in a subfolder or root
    # We want to make sure blastem.exe is directly in $blastemDir
    $subDir = Get-ChildItem -Path $blastemDir -Directory | Select-Object -First 1
    if ($subDir -and (Test-Path "$($subDir.FullName)\blastem.exe")) {
        Get-ChildItem -Path "$($subDir.FullName)\*" | Move-Item -Destination $blastemDir -Force
        Remove-Item -Path $subDir.FullName -Recurse -Force
    }

    Remove-Item -Path $zipPath
    Write-Host "BlastEm configurado em $blastemDir" -ForegroundColor Green
}
else {
    Write-Host "BlastEm já está instalado em $blastemDir" -ForegroundColor Green
}
