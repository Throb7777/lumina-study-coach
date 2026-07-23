[CmdletBinding()]
param(
    [string]$Ref = 'HEAD'
)

$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Version = (Get-Content -LiteralPath (Join-Path $Root 'VERSION') -Raw).Trim()
$Output = Join-Path $Root 'output\release'
$Archive = Join-Path $Output "lumina-study-coach-$Version-source.zip"
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Backend Python environment does not exist. Run uv sync --locked first.'
}

New-Item -ItemType Directory -Force -Path $Output | Out-Null
if (Test-Path -LiteralPath $Archive) {
    Remove-Item -LiteralPath $Archive -Force
}

& git.exe -C $Root archive --format=zip --output=$Archive $Ref
if ($LASTEXITCODE -ne 0) {
    throw "git archive failed for ref: $Ref"
}

& $Python (Join-Path $Root 'scripts\verify_source_archive.py') $Archive
if ($LASTEXITCODE -ne 0) {
    throw 'Source archive verification failed.'
}

$Hash = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash
Write-Host "Source archive: $Archive"
Write-Host "SHA-256: $Hash"
