param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ReferenceImage,
    [Parameter(Mandatory = $true, Position = 1)]
    [string]$CandidateImage,
    [double]$ThresholdPercent = 1.0,
    [string]$OutJson
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ReferenceImage)) {
    throw "Reference image not found: $ReferenceImage"
}
if (-not (Test-Path $CandidateImage)) {
    throw "Candidate image not found: $CandidateImage"
}

Add-Type -AssemblyName System.Drawing

$ref = [System.Drawing.Bitmap]::new($ReferenceImage)
$cand = [System.Drawing.Bitmap]::new($CandidateImage)
try {
    if ($ref.Width -ne $cand.Width -or $ref.Height -ne $cand.Height) {
        throw "Image dimensions differ: ref=$($ref.Width)x$($ref.Height), candidate=$($cand.Width)x$($cand.Height)"
    }

    $width = $ref.Width
    $height = $ref.Height
    $total = $width * $height
    $diff = 0

    for ($y = 0; $y -lt $height; $y++) {
        for ($x = 0; $x -lt $width; $x++) {
            if ($ref.GetPixel($x, $y).ToArgb() -ne $cand.GetPixel($x, $y).ToArgb()) {
                $diff++
            }
        }
    }

    $percent = if ($total -gt 0) { [Math]::Round(($diff * 100.0) / $total, 4) } else { 0.0 }
    $result = [ordered]@{
        reference = (Resolve-Path $ReferenceImage).Path
        candidate = (Resolve-Path $CandidateImage).Path
        width = $width
        height = $height
        total_pixels = $total
        diff_pixels = $diff
        diff_percent = $percent
        threshold_percent = $ThresholdPercent
        pass = ($percent -le $ThresholdPercent)
    }

    $json = $result | ConvertTo-Json -Depth 4
    if ($OutJson) {
        Set-Content -Path $OutJson -Value $json -Encoding UTF8
    }
    Write-Output $json
}
finally {
    $ref.Dispose()
    $cand.Dispose()
}
