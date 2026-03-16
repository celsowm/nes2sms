param(
    [Parameter(Mandatory = $true)]
    [string]$NesRom,
    [Parameter(Mandatory = $true)]
    [string]$SmsProjectDir,
    [string]$OutDir,
    [int]$Frame = 120,
    [string]$NesEmulatorPath,
    [string]$SmsEmulatorPath
)

$ErrorActionPreference = "Stop"

function Write-PngCrop {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputPath,
        [Parameter(Mandatory = $true)]
        [string]$OutputPath,
        [Parameter(Mandatory = $true)]
        [int]$Width,
        [Parameter(Mandatory = $true)]
        [int]$Height
    )

    Add-Type -AssemblyName System.Drawing
    $src = [System.Drawing.Bitmap]::new($InputPath)
    try {
        $cropX = [Math]::Max(0, [int](($src.Width - $Width) / 2))
        $cropY = [Math]::Max(0, [int](($src.Height - $Height) / 2))
        $rect = [System.Drawing.Rectangle]::new($cropX, $cropY, [Math]::Min($Width, $src.Width), [Math]::Min($Height, $src.Height))
        $dst = New-Object System.Drawing.Bitmap($rect.Width, $rect.Height)
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($dst)
            try {
                $graphics.DrawImage($src, 0, 0, $rect, [System.Drawing.GraphicsUnit]::Pixel)
            }
            finally {
                $graphics.Dispose()
            }
            $dst.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
        }
        finally {
            $dst.Dispose()
        }
    }
    finally {
        $src.Dispose()
    }
}

function Get-ImageMetrics {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [int]$TopCount = 5
    )

    Add-Type -AssemblyName System.Drawing
    $image = [System.Drawing.Bitmap]::new($Path)
    try {
        $centerX = [int]($image.Width / 2)
        $centerY = [int]($image.Height / 2)
        $topLeft = $image.GetPixel(0, 0)
        $center = $image.GetPixel($centerX, $centerY)
        $counts = @{}

        for ($y = 0; $y -lt $image.Height; $y++) {
            for ($x = 0; $x -lt $image.Width; $x++) {
                $pixel = $image.GetPixel($x, $y)
                $key = "{0},{1},{2}" -f $pixel.R, $pixel.G, $pixel.B
                if ($counts.ContainsKey($key)) {
                    $counts[$key]++
                }
                else {
                    $counts[$key] = 1
                }
            }
        }

        $dominant = $counts.GetEnumerator() |
            Sort-Object Value -Descending |
            Select-Object -First $TopCount |
            ForEach-Object {
                $rgb = $_.Key.Split(",") | ForEach-Object { [int]$_ }
                [ordered]@{
                    count = [int]$_.Value
                    rgb = $rgb
                }
            }

        return [ordered]@{
            path = [System.IO.Path]::GetFullPath($Path)
            size = @($image.Width, $image.Height)
            top_left_rgb = @($topLeft.R, $topLeft.G, $topLeft.B)
            center_rgb = @($center.R, $center.G, $center.B)
            dominant_colors = $dominant
        }
    }
    finally {
        $image.Dispose()
    }
}

Add-Type -AssemblyName System.Drawing

$baseDir = $PSScriptRoot
if (-not $OutDir) {
    $OutDir = Join-Path -Path $baseDir -ChildPath "tmp\pong_compare"
}
$resolvedOutDir = [System.IO.Path]::GetFullPath($OutDir)
New-Item -ItemType Directory -Force -Path $resolvedOutDir | Out-Null

$rawNesPng = Join-Path -Path $resolvedOutDir -ChildPath "nes_raw_reference.png"
$nesPng = Join-Path -Path $resolvedOutDir -ChildPath "nes_frame.png"
$smsPng = Join-Path -Path $resolvedOutDir -ChildPath "sms_frame.png"
$rawNesCrop = Join-Path -Path $resolvedOutDir -ChildPath "nes_raw_reference_cropped.png"
$nesCrop = Join-Path -Path $resolvedOutDir -ChildPath "nes_frame_cropped.png"
$smsCrop = Join-Path -Path $resolvedOutDir -ChildPath "sms_frame_cropped.png"
$smsDebugDir = Join-Path -Path $resolvedOutDir -ChildPath "sms_debug"
$rawReportJson = Join-Path -Path $resolvedOutDir -ChildPath "raw_reference_report.json"
$diffJson = Join-Path -Path $resolvedOutDir -ChildPath "pixel_diff.json"
$colorJson = Join-Path -Path $resolvedOutDir -ChildPath "color_report.json"
$rawDiffJson = Join-Path -Path $resolvedOutDir -ChildPath "pixel_diff_raw.json"
$windowDiffJson = Join-Path -Path $resolvedOutDir -ChildPath "pixel_diff_window.json"

& (Join-Path -Path $baseDir -ChildPath "capture_nes_raw_frame.ps1") `
    -NesRom $NesRom `
    -OutPng $rawNesPng `
    -OutReport $rawReportJson `
    -Frame $Frame `
    -EmulatorPath $NesEmulatorPath

& (Join-Path -Path $baseDir -ChildPath "capture_nes_frame.ps1") `
    -NesRom $NesRom `
    -OutPng $nesPng `
    -Frame $Frame `
    -EmulatorPath $NesEmulatorPath

& (Join-Path -Path $baseDir -ChildPath "capture_sms_frame.ps1") `
    -ProjectDir $SmsProjectDir `
    -OutPng $smsPng `
    -EmulatorPath $SmsEmulatorPath

& (Join-Path -Path $baseDir -ChildPath "capture_sms_debug_artifacts.ps1") `
    -ProjectDir $SmsProjectDir `
    -OutDir $smsDebugDir `
    -EmulatorPath $SmsEmulatorPath | Out-Null

$rawNesImage = [System.Drawing.Bitmap]::new($rawNesPng)
$nesImage = [System.Drawing.Bitmap]::new($nesPng)
$smsImage = [System.Drawing.Bitmap]::new($smsPng)
try {
    $cropWidth = [Math]::Min([Math]::Min($rawNesImage.Width, $nesImage.Width), $smsImage.Width)
    $cropHeight = [Math]::Min([Math]::Min($rawNesImage.Height, $nesImage.Height), $smsImage.Height)
    Write-PngCrop -InputPath $rawNesPng -OutputPath $rawNesCrop -Width $cropWidth -Height $cropHeight
    Write-PngCrop -InputPath $nesPng -OutputPath $nesCrop -Width $cropWidth -Height $cropHeight
    Write-PngCrop -InputPath $smsPng -OutputPath $smsCrop -Width $cropWidth -Height $cropHeight
}
finally {
    $rawNesImage.Dispose()
    $nesImage.Dispose()
    $smsImage.Dispose()
}

& (Join-Path -Path $baseDir -ChildPath "measure_pixel_diff.ps1") `
    -ReferenceImage $rawNesCrop `
    -CandidateImage $smsCrop `
    -OutJson $rawDiffJson | Out-Null

& (Join-Path -Path $baseDir -ChildPath "measure_pixel_diff.ps1") `
    -ReferenceImage $nesCrop `
    -CandidateImage $smsCrop `
    -OutJson $windowDiffJson | Out-Null

$rawReferenceReport = Get-Content -Path $rawReportJson -Raw | ConvertFrom-Json
$rawReferenceMetrics = [ordered]@{
    path = [System.IO.Path]::GetFullPath($rawNesCrop)
    size = @($rawReferenceReport.size[0], $rawReferenceReport.size[1])
    top_left_rgb = @($rawReferenceReport.top_left_rgb[0], $rawReferenceReport.top_left_rgb[1], $rawReferenceReport.top_left_rgb[2])
    center_rgb = @($rawReferenceReport.center_rgb[0], $rawReferenceReport.center_rgb[1], $rawReferenceReport.center_rgb[2])
    dominant_colors = @($rawReferenceReport.dominant_colors)
    source = $rawReferenceReport.source
    render_mode = $rawReferenceReport.render_mode
    has_useful_nametable = [bool]$rawReferenceReport.has_useful_nametable
    nonzero_nametable_bytes = [int]$rawReferenceReport.nonzero_nametable_bytes
    sprite_count = [int]$rawReferenceReport.sprite_count
    background_rgb = @($rawReferenceReport.background_rgb[0], $rawReferenceReport.background_rgb[1], $rawReferenceReport.background_rgb[2])
}
$nesMetrics = Get-ImageMetrics -Path $nesCrop
$smsMetrics = Get-ImageMetrics -Path $smsCrop
$rawCenterDelta = for ($i = 0; $i -lt 3; $i++) {
    [Math]::Abs([int]$rawReferenceMetrics.center_rgb[$i] - [int]$smsMetrics.center_rgb[$i])
}
$rawTopLeftDelta = for ($i = 0; $i -lt 3; $i++) {
    [Math]::Abs([int]$rawReferenceMetrics.top_left_rgb[$i] - [int]$smsMetrics.top_left_rgb[$i])
}
$windowCenterDelta = for ($i = 0; $i -lt 3; $i++) {
    [Math]::Abs([int]$nesMetrics.center_rgb[$i] - [int]$smsMetrics.center_rgb[$i])
}
$windowTopLeftDelta = for ($i = 0; $i -lt 3; $i++) {
    [Math]::Abs([int]$nesMetrics.top_left_rgb[$i] - [int]$smsMetrics.top_left_rgb[$i])
}
$rawDiff = Get-Content -Path $rawDiffJson -Raw | ConvertFrom-Json
$windowDiff = Get-Content -Path $windowDiffJson -Raw | ConvertFrom-Json
$combinedDiff = [ordered]@{
    approval_mode = "raw_reference"
    raw_reference_report = $rawDiff
    emulator_window_report = $windowDiff
    pass = [bool]$rawDiff.pass
}
($combinedDiff | ConvertTo-Json -Depth 6) | Set-Content -Path $diffJson -Encoding UTF8

$colorReport = [ordered]@{
    approval_mode = "raw_reference"
    raw_reference_report = [ordered]@{
        nes = $rawReferenceMetrics
        sms = $smsMetrics
        center_delta = $rawCenterDelta
        top_left_delta = $rawTopLeftDelta
    }
    emulator_window_report = [ordered]@{
        nes = $nesMetrics
        sms = $smsMetrics
        center_delta = $windowCenterDelta
        top_left_delta = $windowTopLeftDelta
        informational_only = $true
        note = "Window screenshot can include emulator presentation effects and does not gate pass/fail."
    }
}
($colorReport | ConvertTo-Json -Depth 6) | Set-Content -Path $colorJson -Encoding UTF8

Write-Host "Comparison artifacts:" -ForegroundColor Cyan
Write-Host "  NES raw reference : $rawNesPng"
Write-Host "  NES : $nesPng"
Write-Host "  SMS : $smsPng"
Write-Host "  NES raw cropped : $rawNesCrop"
Write-Host "  NES cropped : $nesCrop"
Write-Host "  SMS cropped : $smsCrop"
Write-Host "  SMS debug : $smsDebugDir"
Write-Host "  Diff : $diffJson"
Write-Host "  Color report : $colorJson"
Write-Host ""
Write-Host "Raw-reference summary:" -ForegroundColor Cyan
Write-Host "  Render mode     : $($rawReferenceMetrics.render_mode)"
Write-Host "  Nametable bytes : $($rawReferenceMetrics.nonzero_nametable_bytes)"
Write-Host "  Sprites         : $($rawReferenceMetrics.sprite_count)"
Write-Host "  NES center RGB  : $($colorReport.raw_reference_report.nes.center_rgb -join ', ')"
Write-Host "  SMS center RGB  : $($colorReport.raw_reference_report.sms.center_rgb -join ', ')"
Write-Host "  Center delta    : $($colorReport.raw_reference_report.center_delta -join ', ')"
Write-Host "  NES dominant    : $($colorReport.raw_reference_report.nes.dominant_colors[0].rgb -join ', ')"
Write-Host "  SMS dominant    : $($colorReport.raw_reference_report.sms.dominant_colors[0].rgb -join ', ')"
Write-Host "  Pass            : $($combinedDiff.pass)"
Write-Host ""
Write-Host "Emulator-window summary (informational):" -ForegroundColor Cyan
Write-Host "  NES center RGB  : $($colorReport.emulator_window_report.nes.center_rgb -join ', ')"
Write-Host "  SMS center RGB  : $($colorReport.emulator_window_report.sms.center_rgb -join ', ')"
Write-Host "  Center delta    : $($colorReport.emulator_window_report.center_delta -join ', ')"
