param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ProjectDir,
    [string]$OutDir,
    [string]$EmulatorPath,
    [switch]$KeepEmulatorOpen
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

function Ensure-WindowCaptureType {
    if (([System.Management.Automation.PSTypeName]'Win32WindowCapture').Type) {
        return
    }

    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class Win32WindowCapture
{
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool PrintWindow(IntPtr hwnd, IntPtr hDC, uint nFlags);

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

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count);

    [DllImport("user32.dll")]
    public static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out int lpdwProcessId);
}
"@
}

function Wait-MainWindowHandle {
    param(
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$Process,
        [int]$TimeoutMs = 15000
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
        Start-Sleep -Milliseconds 200
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

    Ensure-WindowCaptureType
    [void][Win32WindowCapture]::SetForegroundWindow($WindowHandle)
    $wshell = New-Object -ComObject WScript.Shell
    [void]$wshell.AppActivate($ProcessId)
    Start-Sleep -Milliseconds 180

    $foreground = [Win32WindowCapture]::GetForegroundWindow()
    return ($foreground -eq $WindowHandle)
}

function Send-EmulatorKey {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle,
        [Parameter(Mandatory = $true)]
        [char]$KeyChar
    )

    Ensure-WindowCaptureType
    $WM_KEYDOWN = 0x0100
    $WM_KEYUP = 0x0101
    $WM_CHAR = 0x0102
    $KEYEVENTF_KEYUP = 0x0002
    $vk = [int][char]([string]$KeyChar).ToUpperInvariant()
    $scan = [byte]([Win32WindowCapture]::MapVirtualKey([uint32]$vk, 0))
    [void][Win32WindowCapture]::SetForegroundWindow($WindowHandle)

    [void][Win32WindowCapture]::PostMessage($WindowHandle, $WM_KEYDOWN, [IntPtr]$vk, [IntPtr]::Zero)
    Start-Sleep -Milliseconds 40
    [void][Win32WindowCapture]::PostMessage($WindowHandle, $WM_CHAR, [IntPtr]([int][char]$KeyChar), [IntPtr]::Zero)
    [void][Win32WindowCapture]::PostMessage($WindowHandle, $WM_KEYUP, [IntPtr]$vk, [IntPtr]::Zero)
    [Win32WindowCapture]::keybd_event([byte]$vk, $scan, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 30
    [Win32WindowCapture]::keybd_event([byte]$vk, $scan, $KEYEVENTF_KEYUP, [UIntPtr]::Zero)

    # Some BlastEm builds react only to translated foreground input.
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.SendKeys]::SendWait(([string]$KeyChar))
    }
    catch {
        # Keep PostMessage path as baseline.
    }
}

function Save-WindowPng {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle,
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if ($WindowHandle -eq [IntPtr]::Zero) {
        throw "Cannot capture image: invalid emulator window handle."
    }

    Ensure-WindowCaptureType
    Add-Type -AssemblyName System.Drawing

    $rect = New-Object Win32WindowCapture+RECT
    $hasRect = [Win32WindowCapture]::GetWindowRect($WindowHandle, [ref]$rect)
    if (-not $hasRect) {
        throw "Cannot capture image: failed to read BlastEm window bounds."
    }

    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($width -le 0 -or $height -le 0) {
        throw "Cannot capture image: BlastEm window bounds are invalid."
    }

    $bmp = New-Object System.Drawing.Bitmap($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bmp)
    $hDc = $graphics.GetHdc()

    try {
        $printed = [Win32WindowCapture]::PrintWindow($WindowHandle, $hDc, 0)
    }
    finally {
        $graphics.ReleaseHdc($hDc)
    }

    if (-not $printed) {
        $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, $bmp.Size)
    }

    try {
        $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $graphics.Dispose()
        $bmp.Dispose()
    }
}

function Validate-CapturedImages {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$ImagePaths
    )

    $missing = $ImagePaths | Where-Object { -not (Test-Path $_) }
    if ($missing.Count -gt 0) {
        throw "Capture validation failed: missing image files: $($missing -join ', ')"
    }

    $hashes = $ImagePaths | ForEach-Object {
        (Get-FileHash -Path $_ -Algorithm SHA256).Hash
    }

    if ($hashes[0] -eq $hashes[1]) {
        throw "Capture validation failed: GAME and VRAM screenshots are identical. BlastEm VRAM hotkey likely was not captured."
    }
    if ($hashes[1] -eq $hashes[2]) {
        throw "Capture validation failed: VRAM and CRAM screenshots are identical. BlastEm CRAM hotkey likely was not captured."
    }
}

function Get-WindowTitle {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle
    )

    Ensure-WindowCaptureType
    $len = [Win32WindowCapture]::GetWindowTextLength($WindowHandle)
    if ($len -le 0) {
        return ""
    }
    $sb = New-Object System.Text.StringBuilder ($len + 1)
    [void][Win32WindowCapture]::GetWindowText($WindowHandle, $sb, $sb.Capacity)
    return $sb.ToString()
}

function Validate-WindowOrigin {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle,
        [Parameter(Mandatory = $true)]
        [int]$ProcessId
    )

    Ensure-WindowCaptureType
    $ownerPid = 0
    [void][Win32WindowCapture]::GetWindowThreadProcessId($WindowHandle, [ref]$ownerPid)
    if ($ownerPid -ne $ProcessId) {
        throw "Capture failed: target window does not belong to BlastEm process (expected PID $ProcessId, got PID $ownerPid)."
    }

    $title = Get-WindowTitle -WindowHandle $WindowHandle
    if ([string]::IsNullOrWhiteSpace($title)) {
        throw "Capture failed: BlastEm main window title is empty; cannot validate capture origin."
    }

    return $title
}

function Capture-DebugView {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle,
        [Parameter(Mandatory = $true)]
        [char]$KeyChar,
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string[]]$PreviousHashes,
        [Parameter(Mandatory = $true)]
        [string]$ViewName,
        [int]$Attempts = 3
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        Send-EmulatorKey -WindowHandle $WindowHandle -KeyChar $KeyChar
        Start-Sleep -Milliseconds (450 + ($attempt * 180))
        Save-WindowPng -WindowHandle $WindowHandle -Path $Path
        $hash = (Get-FileHash -Path $Path -Algorithm SHA256).Hash
        if ($PreviousHashes -notcontains $hash) {
            return $hash
        }
    }

    throw "Capture validation failed: could not produce a distinct $ViewName screenshot after $Attempts attempt(s)."
}

function Get-ImageHash {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )
    return (Get-FileHash -Path $Path -Algorithm SHA256).Hash
}

function Capture-FrameHash {
    param(
        [Parameter(Mandatory = $true)]
        [IntPtr]$WindowHandle,
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    Save-WindowPng -WindowHandle $WindowHandle -Path $Path
    return Get-ImageHash -Path $Path
}

function Copy-IfExists {
    param(
        [string]$Source,
        [string]$Dest
    )
    if (Test-Path $Source) {
        Copy-Item -Path $Source -Destination $Dest -Force
    }
}

function Write-HexPreview {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceFile,
        [Parameter(Mandatory = $true)]
        [string]$DestFile,
        [int]$MaxBytes = 256
    )

    if (-not (Test-Path $SourceFile)) {
        return
    }

    $fileBytes = [System.IO.File]::ReadAllBytes($SourceFile)
    $take = [Math]::Min($MaxBytes, $fileBytes.Length)
    if ($take -le 0) {
        Set-Content -Path $DestFile -Value @() -Encoding UTF8
        return
    }
    $slice = $fileBytes[0..($take - 1)]

    $lines = @()
    for ($i = 0; $i -lt $slice.Length; $i += 16) {
        $chunk = $slice[$i..([Math]::Min($i + 15, $slice.Length - 1))]
        $hex = ($chunk | ForEach-Object { "{0:X2}" -f $_ }) -join " "
        $lines += ("{0:X4}: {1}" -f $i, $hex)
    }

    Set-Content -Path $DestFile -Value $lines -Encoding UTF8
}

function Write-VdpRegisterDump {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AsmFile,
        [Parameter(Mandatory = $true)]
        [string]$DestFile
    )

    if (-not (Test-Path $AsmFile)) {
        Set-Content -Path $DestFile -Value @("VDP register dump unavailable: source file not found.") -Encoding UTF8
        return
    }

    $lines = Get-Content -Path $AsmFile
    $dump = @()
    $dump += "[VDP register intent]"
    $dump += (Select-String -InputObject $lines -Pattern "Register [0-9]+:" | ForEach-Object { $_.Line.Trim() })
    $dump += ""
    $dump += "[VDP write instructions]"
    $dump += (Select-String -InputObject $lines -Pattern "ld\s+a,\s*[0-9]+|ld\s+b,\s*[%$0-9A-Fa-f]+|call\s+VDP_WriteReg" | ForEach-Object { $_.Line.Trim() })
    if ($dump.Count -eq 0) {
        $dump = @("No VDP register lines detected in source.")
    }
    Set-Content -Path $DestFile -Value $dump -Encoding UTF8
}

function Write-SpriteListDump {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SatYPath,
        [Parameter(Mandatory = $true)]
        [string]$SatXtPath,
        [Parameter(Mandatory = $true)]
        [string]$DestFile
    )

    if (-not (Test-Path $SatYPath) -or -not (Test-Path $SatXtPath)) {
        Set-Content -Path $DestFile -Value @("Sprite list unavailable: sat_y.bin or sat_xt.bin missing.") -Encoding UTF8
        return
    }

    $y = [System.IO.File]::ReadAllBytes($SatYPath)
    $xt = [System.IO.File]::ReadAllBytes($SatXtPath)
    $maxSprites = [Math]::Min(64, $y.Length)
    $lines = @("idx y x tile")

    for ($i = 0; $i -lt $maxSprites; $i++) {
        $yy = $y[$i]
        if ($yy -eq 0xD0) {
            $lines += "-- terminator at index $i --"
            break
        }
        $xtOffset = $i * 2
        if ($xtOffset + 1 -ge $xt.Length) {
            $lines += "-- truncated xt table at sprite $i --"
            break
        }
        $xx = $xt[$xtOffset]
        $tt = $xt[$xtOffset + 1]
        $lines += ("{0:D2} ${1:X2} ${2:X2} ${3:X2}" -f $i, $yy, $xx, $tt)
    }

    Set-Content -Path $DestFile -Value $lines -Encoding UTF8
}

$baseDir = $PSScriptRoot
$resolvedProject = Resolve-ProjectPath -BaseDir $baseDir -Dir $ProjectDir
$romPath = Find-RomFile -ProjectPath $resolvedProject

if (-not $romPath) {
    throw "No SMS ROM found in '$resolvedProject'. Build first."
}

if (-not $OutDir) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $OutDir = Join-Path $resolvedProject "debug_artifacts\$timestamp"
}
if (-not [System.IO.Path]::IsPathRooted($OutDir)) {
    $OutDir = Join-Path $baseDir $OutDir
}

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

$asmOut = Join-Path $OutDir "asm"
$binOut = Join-Path $OutDir "bin"
$imgOut = Join-Path $OutDir "images"
New-Item -ItemType Directory -Path $asmOut -Force | Out-Null
New-Item -ItemType Directory -Path $binOut -Force | Out-Null
New-Item -ItemType Directory -Path $imgOut -Force | Out-Null

Write-Host "=== Collecting static artifacts ===" -ForegroundColor Cyan
Write-Host "Project: $resolvedProject"
Write-Host "ROM    : $romPath"
Write-Host "OutDir : $OutDir"

$buildDir = Join-Path $resolvedProject "build"
Copy-IfExists (Join-Path $buildDir "stubs\game_logic.asm") (Join-Path $asmOut "game_logic.asm")
Copy-IfExists (Join-Path $buildDir "hal\support.asm") (Join-Path $asmOut "support.asm")
Copy-IfExists (Join-Path $buildDir "hal\vdp.asm") (Join-Path $asmOut "vdp.asm")
Copy-IfExists (Join-Path $buildDir "assets.asm") (Join-Path $asmOut "assets.asm")
Copy-IfExists (Join-Path $buildDir "init.asm") (Join-Path $asmOut "init.asm")
Copy-IfExists (Join-Path $buildDir "interrupts.asm") (Join-Path $asmOut "interrupts.asm")

Copy-IfExists (Join-Path $buildDir "assets\palette_bg.bin") (Join-Path $binOut "palette_bg.bin")
Copy-IfExists (Join-Path $buildDir "assets\palette_spr.bin") (Join-Path $binOut "palette_spr.bin")
Copy-IfExists (Join-Path $buildDir "assets\tiles.bin") (Join-Path $binOut "tiles.bin")
Copy-IfExists (Join-Path $buildDir "assets\sat_y.bin") (Join-Path $binOut "sat_y.bin")
Copy-IfExists (Join-Path $buildDir "assets\sat_xt.bin") (Join-Path $binOut "sat_xt.bin")
Copy-IfExists (Join-Path $buildDir "assets\sprite_variant_map.bin") (Join-Path $binOut "sprite_variant_map.bin")

if (-not (Test-Path (Join-Path $binOut "sat_y.bin"))) {
    [System.IO.File]::WriteAllBytes((Join-Path $binOut "sat_y.bin"), [byte[]](0xD0))
}
if (-not (Test-Path (Join-Path $binOut "sat_xt.bin"))) {
    [System.IO.File]::WriteAllBytes((Join-Path $binOut "sat_xt.bin"), [byte[]]@())
}
if (-not (Test-Path (Join-Path $binOut "sprite_variant_map.bin"))) {
    $defaultVariantMap = New-Object byte[] (256 * 16)
    for ($tile = 0; $tile -lt 256; $tile++) {
        for ($combo = 0; $combo -lt 16; $combo++) {
            $defaultVariantMap[$tile * 16 + $combo] = [byte]$tile
        }
    }
    [System.IO.File]::WriteAllBytes((Join-Path $binOut "sprite_variant_map.bin"), $defaultVariantMap)
}

Write-HexPreview -SourceFile (Join-Path $binOut "palette_bg.bin") -DestFile (Join-Path $binOut "palette_bg.hex.txt") -MaxBytes 64
Write-HexPreview -SourceFile (Join-Path $binOut "palette_spr.bin") -DestFile (Join-Path $binOut "palette_spr.hex.txt") -MaxBytes 64
Write-HexPreview -SourceFile (Join-Path $binOut "tiles.bin") -DestFile (Join-Path $binOut "tiles_first256.hex.txt") -MaxBytes 256
Write-HexPreview -SourceFile (Join-Path $binOut "sat_y.bin") -DestFile (Join-Path $binOut "sat_y.hex.txt") -MaxBytes 64
Write-HexPreview -SourceFile (Join-Path $binOut "sat_xt.bin") -DestFile (Join-Path $binOut "sat_xt.hex.txt") -MaxBytes 128
Write-HexPreview -SourceFile (Join-Path $binOut "sprite_variant_map.bin") -DestFile (Join-Path $binOut "sprite_variant_map.hex.txt") -MaxBytes 256

Write-VdpRegisterDump -AsmFile (Join-Path $asmOut "vdp.asm") -DestFile (Join-Path $binOut "vdp_registers.dump.txt")
Write-SpriteListDump -SatYPath (Join-Path $binOut "sat_y.bin") -SatXtPath (Join-Path $binOut "sat_xt.bin") -DestFile (Join-Path $binOut "sprite_list.dump.txt")

$summaryPath = Join-Path $OutDir "summary.txt"
$summaryJsonPath = Join-Path $OutDir "summary.json"
$summaryLines = @()
$summaryLines += "Project: $resolvedProject"
$summaryLines += "ROM: $romPath"
$summaryLines += "Generated: $(Get-Date -Format s)"
$summaryLines += ""

$summary = [ordered]@{
    status = "static_only"
    project = $resolvedProject
    rom = $romPath
    generated_at = (Get-Date -Format s)
    artifacts = [ordered]@{
        asm = $asmOut
        bin = $binOut
        images = $imgOut
    }
    mandatory = [ordered]@{
        palette_bg_hex = Test-Path (Join-Path $binOut "palette_bg.hex.txt")
        palette_spr_hex = Test-Path (Join-Path $binOut "palette_spr.hex.txt")
        tiles_first256_hex = Test-Path (Join-Path $binOut "tiles_first256.hex.txt")
        vdp_register_dump = Test-Path (Join-Path $binOut "vdp_registers.dump.txt")
        sprite_list_dump = Test-Path (Join-Path $binOut "sprite_list.dump.txt")
        sat_y = Test-Path (Join-Path $binOut "sat_y.bin")
        sat_xt = Test-Path (Join-Path $binOut "sat_xt.bin")
    }
    capture = [ordered]@{
        attempted = $false
        emulator_path = $null
        window_title = $null
        frame_hashes = [ordered]@{}
        attempts = @()
    }
}

$gameLogic = Join-Path $asmOut "game_logic.asm"
$supportAsm = Join-Path $asmOut "support.asm"
if (Test-Path $gameLogic) {
    $summaryLines += "[game_logic checks]"
    $summaryLines += (Select-String -Path $gameLogic -Pattern "JP   P, loop0|JP   P, loop2|JP   NC, sub_826A|sub_817E|NMI_Handler|TODO: BRK" | ForEach-Object { $_.Line.Trim() })
    $summaryLines += ""
}
if (Test-Path $supportAsm) {
    $summaryLines += "[support checks]"
    $summaryLines += (Select-String -Path $supportAsm -SimpleMatch -Pattern "_ppu_2007_nametable:", "_ppu_2007_attribute:", "_ppu_set_vdp_increment", "out  (`$BE), a" | ForEach-Object { $_.Line.Trim() })
    $summaryLines += ""
}

Set-Content -Path $summaryPath -Value $summaryLines -Encoding UTF8

$resolvedEmulator = Find-Emulator -BaseDir $baseDir -CustomPath $EmulatorPath
if (-not $resolvedEmulator) {
    Write-Host "WARNING: BlastEm not found. Static artifacts collected only." -ForegroundColor Yellow
    $summary.capture.attempted = $false
    $summary.status = "static_only"
    $summary | ConvertTo-Json -Depth 8 | Set-Content -Path $summaryJsonPath -Encoding UTF8
    Write-Host "Done. Artifacts written to: $OutDir" -ForegroundColor Green
    exit 0
}

Write-Host "=== Capturing emulator artifacts ===" -ForegroundColor Cyan
Write-Host "Emulator: $resolvedEmulator"
$summary.capture.attempted = $true
$summary.capture.emulator_path = $resolvedEmulator
$summary.status = "capture_partial"

$process = $null
try {
    $attempt = [ordered]@{ step = "launch"; ok = $true; message = ""; pid = $null }
    $process = Start-Process -FilePath $resolvedEmulator -ArgumentList @("-m", "sms", $romPath) -PassThru
    $attempt.pid = $process.Id
    $summary.capture.attempts += $attempt
    Start-Sleep -Seconds 3

    $windowHandle = Wait-MainWindowHandle -Process $process
    if ($windowHandle -eq [IntPtr]::Zero) {
        throw "Window handle not available."
    }
    $windowTitle = Validate-WindowOrigin -WindowHandle $windowHandle -ProcessId $process.Id
    $summary.capture.window_title = $windowTitle
    $summary.capture.attempts += [ordered]@{ step = "window_ready"; ok = $true; message = "Window validated."; pid = $process.Id }

    Ensure-WindowCaptureType
    [void][Win32WindowCapture]::SetForegroundWindow($windowHandle)
    $focused = Focus-EmulatorWindow -WindowHandle $windowHandle -ProcessId $process.Id
    if (-not $focused) {
        $summary.capture.attempts += [ordered]@{ step = "focus"; ok = $false; message = "Foreground focus not guaranteed."; pid = $process.Id }
    }
    else {
        $summary.capture.attempts += [ordered]@{ step = "focus"; ok = $true; message = "Foreground focus acquired."; pid = $process.Id }
    }

    $imgGame = Join-Path $imgOut "00_game.png"
    $imgVram = Join-Path $imgOut "01_vram_debug.png"
    $imgCram = Join-Path $imgOut "02_cram_debug.png"

    try {
        $hashGame = Capture-FrameHash -WindowHandle $windowHandle -Path $imgGame
        $summary.capture.frame_hashes["game"] = $hashGame
        $summary.capture.attempts += [ordered]@{ step = "capture_game"; ok = $true; message = "Game frame captured."; pid = $process.Id }
    }
    catch {
        $summary.capture.attempts += [ordered]@{ step = "capture_game"; ok = $false; message = $_.Exception.Message; pid = $process.Id }
    }

    # Optional debug views (best effort only).
    try {
        Send-EmulatorKey -WindowHandle $windowHandle -KeyChar 'u'
        Start-Sleep -Milliseconds 500
        $prev = @()
        if ($summary.capture.frame_hashes["game"]) {
            $prev = @($summary.capture.frame_hashes["game"])
        }
        $hashVram = Capture-DebugView -WindowHandle $windowHandle -KeyChar 'v' -Path $imgVram -PreviousHashes $prev -ViewName "VRAM"
        $summary.capture.frame_hashes["vram"] = $hashVram
        $summary.capture.attempts += [ordered]@{ step = "capture_vram_optional"; ok = $true; message = "VRAM debug view captured."; pid = $process.Id }
    }
    catch {
        $summary.capture.attempts += [ordered]@{ step = "capture_vram_optional"; ok = $false; message = $_.Exception.Message; pid = $process.Id }
    }

    try {
        $prev = @()
        if ($summary.capture.frame_hashes["game"]) { $prev += $summary.capture.frame_hashes["game"] }
        if ($summary.capture.frame_hashes["vram"]) { $prev += $summary.capture.frame_hashes["vram"] }
        $hashCram = Capture-DebugView -WindowHandle $windowHandle -KeyChar 'c' -Path $imgCram -PreviousHashes $prev -ViewName "CRAM"
        $summary.capture.frame_hashes["cram"] = $hashCram
        $summary.capture.attempts += [ordered]@{ step = "capture_cram_optional"; ok = $true; message = "CRAM debug view captured."; pid = $process.Id }
    }
    catch {
        $summary.capture.attempts += [ordered]@{ step = "capture_cram_optional"; ok = $false; message = $_.Exception.Message; pid = $process.Id }
    }

    if ($summary.capture.frame_hashes["game"]) {
        $summary.status = "ok"
    }
}
catch {
    $summary.capture.attempts += [ordered]@{ step = "capture_error"; ok = $false; message = $_.Exception.Message; pid = $null }
    $summary.status = "capture_failed"
}
finally {
    if (-not $KeepEmulatorOpen -and $process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
}

Add-Content -Path $summaryPath -Value @(
    "[capture checks]",
    "Capture attempted: $($summary.capture.attempted)",
    "Capture status: $($summary.status)",
    "Window title: $($summary.capture.window_title)",
    "Hash GAME: $($summary.capture.frame_hashes['game'])",
    "Hash VRAM(optional): $($summary.capture.frame_hashes['vram'])",
    "Hash CRAM(optional): $($summary.capture.frame_hashes['cram'])",
    ""
)

$mandatoryOk = $true
foreach ($k in $summary.mandatory.Keys) {
    if (-not $summary.mandatory[$k]) {
        $mandatoryOk = $false
    }
}
$summary.mandatory_ok = $mandatoryOk
if (-not $mandatoryOk) {
    $summary.status = "missing_mandatory_artifacts"
}

$summary | ConvertTo-Json -Depth 8 | Set-Content -Path $summaryJsonPath -Encoding UTF8

if (-not $mandatoryOk) {
    throw "Mandatory deterministic artifacts are missing. Check summary.json."
}

Write-Host "Done. Artifacts written to: $OutDir" -ForegroundColor Green
