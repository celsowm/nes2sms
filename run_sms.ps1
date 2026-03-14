param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ProjectDir,
    [string]$EmulatorPath,
    [switch]$DebugCLI,
    [switch]$GdbStub,
    [switch]$SkipKeyboardCapture
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

function Ensure-WindowInputType {
    if (([System.Management.Automation.PSTypeName]'Win32InputBridge').Type) {
        return
    }

    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class Win32InputBridge
{
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll")]
    public static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
}
"@
}

function Wait-MainWindowHandle {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process,
        [int]$TimeoutMs = 12000
    )

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.ElapsedMilliseconds -lt $TimeoutMs) {
        if ($Process.HasExited) {
            return [IntPtr]::Zero
        }

        $Process.Refresh()
        if ($Process.MainWindowHandle -ne [IntPtr]::Zero) {
            return $Process.MainWindowHandle
        }

        Start-Sleep -Milliseconds 180
    }

    return [IntPtr]::Zero
}

function Focus-EmulatorWindow {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle,
        [Parameter(Mandatory = $true)]
        [int]$ProcessId
    )

    Ensure-WindowInputType
    [void][Win32InputBridge]::SetForegroundWindow($WindowHandle)
    try {
        $wshell = New-Object -ComObject WScript.Shell
        [void]$wshell.AppActivate($ProcessId)
    }
    catch {
        # Best effort only.
    }
    Start-Sleep -Milliseconds 140

    $foreground = [Win32InputBridge]::GetForegroundWindow()
    return ($foreground -eq $WindowHandle)
}

function Send-KeyboardCaptureToggle {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle
    )

    Ensure-WindowInputType
    $WM_KEYDOWN = 0x0100
    $WM_KEYUP = 0x0101
    $VK_RCONTROL = 0xA3
    $KEYEVENTF_EXTENDEDKEY = 0x0001
    $KEYEVENTF_KEYUP = 0x0002

    [void][Win32InputBridge]::PostMessage($WindowHandle, $WM_KEYDOWN, [IntPtr]$VK_RCONTROL, [IntPtr]::Zero)
    Start-Sleep -Milliseconds 35
    [void][Win32InputBridge]::PostMessage($WindowHandle, $WM_KEYUP, [IntPtr]$VK_RCONTROL, [IntPtr]::Zero)

    [Win32InputBridge]::keybd_event([byte]$VK_RCONTROL, 0, $KEYEVENTF_EXTENDEDKEY, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 35
    [Win32InputBridge]::keybd_event([byte]$VK_RCONTROL, 0, ($KEYEVENTF_EXTENDEDKEY -bor $KEYEVENTF_KEYUP), [UIntPtr]::Zero)
}

function Try-EnableKeyboardCapture {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process
    )

    if ($SkipKeyboardCapture) {
        Write-Host "Keyboard: skip auto-capture (-SkipKeyboardCapture)." -ForegroundColor Yellow
        Write-Host "Fallback: if controls do not respond, press Right Ctrl in BlastEm." -ForegroundColor Yellow
        return
    }

    Write-Host "Keyboard: trying automatic capture (Right Ctrl)..." -ForegroundColor Cyan
    $windowHandle = Wait-MainWindowHandle -Process $Process
    if ($windowHandle -eq [IntPtr]::Zero) {
        Write-Host "WARNING: could not detect BlastEm window in time." -ForegroundColor Yellow
        Write-Host "Fallback: if controls do not respond, press Right Ctrl in BlastEm." -ForegroundColor Yellow
        return
    }

    $focused = Focus-EmulatorWindow -WindowHandle $windowHandle -ProcessId $Process.Id
    if (-not $focused) {
        Write-Host "WARNING: could not confirm BlastEm window focus before key capture." -ForegroundColor Yellow
    }

    Send-KeyboardCaptureToggle -WindowHandle $windowHandle
    Write-Host "Keyboard: capture toggle sent (1 attempt)." -ForegroundColor Green
    Write-Host "Fallback: if controls still do not respond, press Right Ctrl in BlastEm." -ForegroundColor Yellow
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
Write-Host "  Right Ctrl = capture/release keyboard"
Write-Host ""
Write-Host "Gameplay controls (default): arrows = d-pad, A/S = buttons" -ForegroundColor Cyan

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

$emulatorProcess = Start-Process -FilePath $resolvedEmulator -ArgumentList $argumentString -PassThru
Try-EnableKeyboardCapture -Process $emulatorProcess
