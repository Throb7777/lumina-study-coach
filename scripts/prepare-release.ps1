[CmdletBinding()]
param(
    [string]$Version,
    [string]$SourceRef = 'HEAD'
)

$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$VersionFile = Join-Path $Root 'VERSION'
$ReleaseOutput = Join-Path $Root 'output\release'
$InstallerOutput = Join-Path $Root 'output\installer'
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'

if ([string]::IsNullOrWhiteSpace($Version)) {
    if (-not (Test-Path -LiteralPath $VersionFile -PathType Leaf)) {
        throw 'VERSION file was not found.'
    }
    $Version = (Get-Content -LiteralPath $VersionFile -Raw).Trim()
}
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Release version must use MAJOR.MINOR.PATCH: $Version"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Backend Python environment does not exist.'
}

New-Item -ItemType Directory -Force -Path $ReleaseOutput | Out-Null

& $Python (Join-Path $PSScriptRoot 'build_sbom.py') `
    (Join-Path $ReleaseOutput 'lumina-sbom.cdx.json')
if ($LASTEXITCODE -ne 0) {
    throw 'SBOM generation failed.'
}

& (Join-Path $PSScriptRoot 'package-source.ps1') -Ref $SourceRef
if ($LASTEXITCODE -ne 0) {
    throw 'Source package generation failed.'
}

$Installer = Join-Path $InstallerOutput "install_Lumina-$Version.exe"
$ManifestSource = Join-Path $InstallerOutput 'release-manifest.json'
$Manifest = Join-Path $ReleaseOutput 'release-manifest.json'
$SourceArchive = Join-Path $ReleaseOutput "lumina-study-coach-$Version-source.zip"
$Sbom = Join-Path $ReleaseOutput 'lumina-sbom.cdx.json'

foreach ($requiredPath in @($Installer, $ManifestSource, $SourceArchive, $Sbom)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required release artifact was not found: $requiredPath"
    }
}
Copy-Item -LiteralPath $ManifestSource -Destination $Manifest -Force

$HashTargets = @($Installer, $SourceArchive, $Manifest, $Sbom)
$HashLines = foreach ($target in $HashTargets) {
    $hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $([IO.Path]::GetFileName($target))"
}
$HashFile = Join-Path $ReleaseOutput 'SHA256SUMS.txt'
$HashLines | Set-Content -LiteralPath $HashFile -Encoding Ascii

Write-Host '[DONE] Release assets prepared:'
foreach ($target in $HashTargets + $HashFile) {
    Write-Host "  $target"
}
