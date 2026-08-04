[CmdletBinding()]
param(
    [string]$SourceDirectory
)

$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Destination = Join-Path $Root 'installer\ocr-runtime'
$LockPath = Join-Path $Root 'installer\ocr-runtime.lock.json'
$Lock = Get-Content -LiteralPath $LockPath -Raw | ConvertFrom-Json

if ([string]::IsNullOrWhiteSpace($SourceDirectory)) {
    $command = Get-Command tesseract.exe -ErrorAction SilentlyContinue
    $candidates = @()
    if ($command) { $candidates += Split-Path -Parent $command.Source }
    $candidates += @(
        (Join-Path $env:ProgramFiles 'Tesseract-OCR'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Tesseract-OCR')
    )
    $SourceDirectory = $candidates |
        Where-Object { Test-Path -LiteralPath (Join-Path $_ 'tesseract.exe') -PathType Leaf } |
        Select-Object -First 1
}

if ([string]::IsNullOrWhiteSpace($SourceDirectory)) {
    throw 'Tesseract build runtime was not found. Provide -SourceDirectory with a complete Windows x64 runtime.'
}

$SourceDirectory = [IO.Path]::GetFullPath($SourceDirectory)
$required = @(
    (Join-Path $SourceDirectory 'tesseract.exe'),
    (Join-Path $SourceDirectory 'tessdata\eng.traineddata'),
    (Join-Path $SourceDirectory 'tessdata\chi_sim.traineddata'),
    (Join-Path $SourceDirectory 'tessdata\chi_sim_vert.traineddata')
)
$missing = @($required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
if ($missing.Count -gt 0) {
    throw "OCR source runtime is incomplete: $($missing -join ', ')"
}

foreach ($entry in $Lock.tessdata.files.PSObject.Properties) {
    $path = Join-Path $SourceDirectory "tessdata\$($entry.Name)"
    $actualHash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    if ($actualHash -ne $entry.Value) {
        throw "OCR language file hash mismatch: $($entry.Name)"
    }
}
$expectedEngineVersion = (($Lock.tesseract.version -split '\.')[0..2] -join '.')
$versionOutput = & (Join-Path $SourceDirectory 'tesseract.exe') --version 2>&1 |
    Select-Object -First 1
if ($LASTEXITCODE -ne 0 -or $versionOutput -notmatch "^tesseract v?$([regex]::Escape($expectedEngineVersion))") {
    throw "OCR engine version does not match lock file: expected $expectedEngineVersion"
}

if (Test-Path -LiteralPath $Destination) {
    Remove-Item -LiteralPath $Destination -Recurse -Force
}
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
Copy-Item -Path (Join-Path $SourceDirectory '*') -Destination $Destination -Recurse -Force

$languageOutput = & (Join-Path $Destination 'tesseract.exe') `
    --tessdata-dir (Join-Path $Destination 'tessdata') --list-langs 2>&1 | Out-String
$tesseractExitCode = $LASTEXITCODE
$languages = @($languageOutput -split '\r?\n' | ForEach-Object { $_.Trim() })
if ($tesseractExitCode -ne 0 -or 'eng' -notin $languages -or 'chi_sim' -notin $languages) {
    throw 'Prepared OCR runtime did not report both eng and chi_sim languages.'
}

Write-Host "Prepared bundled OCR runtime: $Destination"
