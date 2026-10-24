param(
    [string]$Text,
    [string]$FromFile,
    [string]$Label = "chat"
)

$logDir = $PSScriptRoot
$logFile = Join-Path $logDir ((Get-Date).ToString("yyyy-MM-dd") + ".txt")
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

if (-not [string]::IsNullOrWhiteSpace($FromFile)) {
    if (-not (Test-Path $FromFile)) {
        throw "File not found: $FromFile"
    }
    $Text = Get-Content -Path $FromFile -Raw
}

if ([string]::IsNullOrWhiteSpace($Text)) {
    $Text = [Console]::In.ReadToEnd()
}

if ([string]::IsNullOrWhiteSpace($Text)) {
    $Text = "[empty message]"
}

$timestamp = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss.fffK")
$entry = @"
[$timestamp] [$Label]
$Text

"@

Add-Content -Path $logFile -Value $entry -Encoding UTF8
Write-Host "Saved chat entry to: $logFile"
