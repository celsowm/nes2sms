param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ProjectDir,
    [string]$EmulatorPath,
    [switch]$DebugCLI,
    [switch]$GdbStub
)

$ErrorActionPreference = "Stop"

function Resolve-ProjectPath {
    param(
        [string]$BaseDir,
        [string]$Dir
    )

    if ([System.IO.Path]::IsPathRooted($Dir)) {
        return (Resolve-Path -Path $Dir).Path
    }

    return (Resolve-Path -Path (Join-Path -Path $BaseDir -ChildPath $Dir)).Path
}

function Find-RomFile {
    param(
        [string]$ProjectPath
    )

    $candidates = @()
    $buildDir = Join-Path -Path $ProjectPath -ChildPath "build"

    if (Test-Path -Path $buildDir) {
        $candidates += Get-ChildItem -Path $buildDir -Filter "*.sms" -File |
            Where-Object { $_.Name -ne "link.sms" -and $_.Length -ge 1024 }
    }

    $candidates += Get-ChildItem -Path $ProjectPath -Filter "*.sms" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne "link.sms" -and $_.Length -ge 1024 }

    if (-not $candidates) {
        return $null
    }

    return ($candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
}

function Find-Emulator {
    param(
        [string]$BaseDir,
        [string]$CustomPath
    )

    if ($CustomPath) {
        if (Test-Path -Path $CustomPath) {
            return (Resolve-Path -Path $CustomPath).Path
        }
        throw "Emulator not found at: $CustomPath"
    }

    $localBlastEm = Join-Path -Path $BaseDir -ChildPath "emulators\blastem\blastem.exe"
    if (Test-Path -Path $localBlastEm) {
        return $localBlastEm
    }

    $fromPath = (Get-Command blastem.exe -ErrorAction SilentlyContinue)
    if ($fromPath) {
        return $fromPath.Source
    }

    return $null
}

function Get-EmulatorHelpText {
    param(
        [string]$ExePath
    )

    try {
        return (& $ExePath -h 2>&1 | Out-String)
    }
    catch {
        return ""
    }
}

$baseDir = $PSScriptRoot
$resolvedProject = Resolve-ProjectPath -BaseDir $baseDir -Dir $ProjectDir
$romPath = Find-RomFile -ProjectPath $resolvedProject

if (-not $romPath) {
    Write-Host "ERROR: no SMS ROM found in '$resolvedProject'." -ForegroundColor Red
    Write-Host "Expected something like '$resolvedProject\build\game.sms'." -ForegroundColor Yellow
    exit 1
}

$resolvedEmulator = Find-Emulator -BaseDir $baseDir -CustomPath $EmulatorPath
if (-not $resolvedEmulator) {
    Write-Host "ERROR: emulator not found." -ForegroundColor Red
    Write-Host "Use -EmulatorPath or install BlastEm in '$baseDir\emulators\blastem\blastem.exe'." -ForegroundColor Yellow
    exit 1
}

Write-Host "=== Running SMS ROM ===" -ForegroundColor Cyan
Write-Host "Project : $resolvedProject"
Write-Host "ROM     : $romPath"
Write-Host "Emulator: $resolvedEmulator"
if ($DebugCLI) {
    Write-Host "Mode    : BlastEm debugger (-d)" -ForegroundColor Yellow
}
if ($GdbStub) {
    Write-Host "Mode    : GDB remote stub (-D)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "BlastEm debug hotkeys:" -ForegroundColor Cyan
Write-Host "  u = enter debugger"
Write-Host "  v = VRAM debug view"
Write-Host "  c = CRAM debug view"
Write-Host "  b = plane debug view"
Write-Host "  n = compositing debug view"
Write-Host "  p = screenshot"

$argumentList = @()
$argumentList += "-m"
$argumentList += "sms"
if ($DebugCLI) {
    $argumentList += "-d"
}
if ($GdbStub) {
    $helpText = Get-EmulatorHelpText -ExePath $resolvedEmulator
    if ($helpText -match "(?m)^\s*-D\b") {
        $argumentList += "-D"
    }
    else {
        Write-Host "WARNING: this BlastEm version does not support -D (GDB stub). Skipping this flag." -ForegroundColor Yellow
    }
}
$argumentList += ('"' + $romPath + '"')
$argumentString = ($argumentList -join " ")
Write-Host "Args    : $argumentString"

Start-Process -FilePath $resolvedEmulator -ArgumentList $argumentString
