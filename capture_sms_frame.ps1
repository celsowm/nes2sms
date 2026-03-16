param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ProjectDir,
    [string]$OutPng,
    [string]$EmulatorPath,
    [int]$WarmupMs = 2500
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

    throw "BlastEm not found."
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

    [DllImport("user32.dll")]
    public static extern uint MapVirtualKey(uint uCode, uint uMapType);
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
    }
    Start-Sleep -Milliseconds 150
}

function Send-EmulatorKey {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle,
        [Parameter(Mandatory = $true)]
        [char]$KeyChar
    )

    Ensure-WindowInputType
    $WM_KEYDOWN = 0x0100
    $WM_KEYUP = 0x0101
    $WM_CHAR = 0x0102
    $KEYEVENTF_KEYUP = 0x0002
    $vk = [int][char]([string]$KeyChar).ToUpperInvariant()
    $scan = [byte]([Win32InputBridge]::MapVirtualKey([uint32]$vk, 0))
    [void][Win32InputBridge]::SetForegroundWindow($WindowHandle)
    [void][Win32InputBridge]::PostMessage($WindowHandle, $WM_KEYDOWN, [IntPtr]$vk, [IntPtr]::Zero)
    Start-Sleep -Milliseconds 40
    [void][Win32InputBridge]::PostMessage($WindowHandle, $WM_CHAR, [IntPtr]([int][char]$KeyChar), [IntPtr]::Zero)
    [void][Win32InputBridge]::PostMessage($WindowHandle, $WM_KEYUP, [IntPtr]$vk, [IntPtr]::Zero)
    [Win32InputBridge]::keybd_event([byte]$vk, $scan, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 30
    [Win32InputBridge]::keybd_event([byte]$vk, $scan, $KEYEVENTF_KEYUP, [UIntPtr]::Zero)
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.SendKeys]::SendWait(([string]$KeyChar))
    }
    catch {
    }
}

function Wait-NewScreenshot {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Directories,
        [datetime]$After,
        [int]$TimeoutSeconds = 10
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $files = foreach ($directory in $Directories) {
            if (-not [string]::IsNullOrWhiteSpace($directory) -and (Test-Path -Path $directory)) {
                Get-ChildItem -Path $directory -Filter "blastem_*.png" -File -ErrorAction SilentlyContinue
            }
        }
        $candidate = $files |
            Where-Object { $_.LastWriteTime -gt $After -and $_.Length -gt 0 } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.FullName
        }
        Start-Sleep -Milliseconds 200
    }

    throw "Timed out waiting for BlastEm internal screenshot."
}

function Capture-InternalScreenshot {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle,
        [Parameter(Mandatory = $true)]
        [string[]]$Directories,
        [Parameter(Mandatory = $true)]
        [datetime]$After,
        [int]$Attempts = 6
    )

    for ($attempt = 0; $attempt -lt $Attempts; $attempt++) {
        Send-EmulatorKey -WindowHandle $WindowHandle -KeyChar 'p'
        try {
            return Wait-NewScreenshot -Directories $Directories -After $After -TimeoutSeconds 5
        }
        catch {
            Start-Sleep -Milliseconds 400
        }
    }

    throw "Timed out waiting for BlastEm internal screenshot."
}

$baseDir = $PSScriptRoot
$resolvedProject = Resolve-ProjectPath -BaseDir $baseDir -Dir $ProjectDir
$romPath = Find-RomFile -ProjectPath $resolvedProject
if (-not $romPath) {
    throw "No SMS ROM found in '$resolvedProject'."
}

if (-not $OutPng) {
    $OutPng = Join-Path -Path $resolvedProject -ChildPath "work\sms_frame.png"
}

$outPath = [System.IO.Path]::GetFullPath($OutPng)
New-Item -ItemType Directory -Force -Path (Split-Path -Path $outPath -Parent) | Out-Null
$screenshotDir = Join-Path -Path (Split-Path -Path $outPath -Parent) -ChildPath "blastem_shots"
New-Item -ItemType Directory -Force -Path $screenshotDir | Out-Null
$resolvedEmulator = Find-Emulator -BaseDir $baseDir -CustomPath $EmulatorPath

$args = @("-m", "sms", $romPath)
$before = Get-Date
$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $resolvedEmulator
$startInfo.Arguments = ($args -join " ")
$startInfo.UseShellExecute = $false
$startInfo.WorkingDirectory = Split-Path -Path $resolvedEmulator -Parent
$startInfo.EnvironmentVariables["HOME"] = $screenshotDir
$process = [System.Diagnostics.Process]::Start($startInfo)
try {
    $windowHandle = Wait-MainWindowHandle -Process $process
    if ($windowHandle -eq [IntPtr]::Zero) {
        throw "Could not detect BlastEm window."
    }

    Start-Sleep -Milliseconds $WarmupMs
    Focus-EmulatorWindow -WindowHandle $windowHandle -ProcessId $process.Id
    $screenshot = Capture-InternalScreenshot `
        -WindowHandle $windowHandle `
        -Directories @($screenshotDir, [Environment]::GetFolderPath("UserProfile")) `
        -After $before
    Copy-Item -Path $screenshot -Destination $outPath -Force
}
finally {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
}

Write-Host "SMS frame captured: $outPath" -ForegroundColor Green
