[CmdletBinding()]
param(
    [string]$Version,
    [switch]$QaBuild,
    [switch]$DiagnosticConsole,
    [switch]$SkipFrontend,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$Output = Join-Path $Root 'output'
$PackageOutput = Join-Path $Output 'release-package'
$WorkOutput = Join-Path $Output 'pyinstaller-work'
$InstallerOutput = Join-Path $Output 'installer'
$Spec = Join-Path $Root 'installer\lumina.spec'
$InnoScript = Join-Path $Root 'installer\Lumina.iss'
$Python = Join-Path $Backend '.venv\Scripts\python.exe'
$VersionFile = Join-Path $Root 'VERSION'

if ([string]::IsNullOrWhiteSpace($Version)) {
    if (-not (Test-Path -LiteralPath $VersionFile -PathType Leaf)) {
        throw 'VERSION file was not found.'
    }
    $Version = (Get-Content -LiteralPath $VersionFile -Raw).Trim()
}
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Release version must use MAJOR.MINOR.PATCH: $Version"
}

function Require-Command([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Required command was not found: $Name"
    }
    return $command.Source
}

function Find-InnoCompiler {
    $command = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }
    throw 'Inno Setup 6 compiler ISCC.exe was not found.'
}

Require-Command 'uv.exe' | Out-Null
if (-not $SkipFrontend) {
    Require-Command 'npm.cmd' | Out-Null
    Push-Location $Frontend
    try {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend locked dependency sync failed.' }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend production build failed.' }
    }
    finally {
        Pop-Location
    }
}

Push-Location $Backend
try {
    & uv.exe sync --locked
    if ($LASTEXITCODE -ne 0) { throw 'Backend locked dependency sync failed.' }
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Backend Python environment does not exist.'
}

foreach ($directory in @($PackageOutput, $WorkOutput)) {
    if (Test-Path -LiteralPath $directory) {
        Remove-Item -LiteralPath $directory -Recurse -Force
    }
}
New-Item -ItemType Directory -Force -Path $PackageOutput, $WorkOutput, $InstallerOutput |
    Out-Null

$VersionParts = @($Version.Split('.') | ForEach-Object { [int]$_ })
$VersionTuple = '{0}, {1}, {2}, 0' -f $VersionParts[0], $VersionParts[1], $VersionParts[2]
$PyInstallerVersionFile = Join-Path $WorkOutput 'lumina-version.txt'
@"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($VersionTuple),
    prodvers=($VersionTuple),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Lumina Contributors'),
          StringStruct('FileDescription', 'Lumina local learning flow coach'),
          StringStruct('FileVersion', '$Version'),
          StringStruct('InternalName', 'Lumina'),
          StringStruct('LegalCopyright', 'Copyright 2026 Lumina Contributors'),
          StringStruct('OriginalFilename', 'Lumina.exe'),
          StringStruct('ProductName', 'Lumina'),
          StringStruct('ProductVersion', '$Version'),
        ],
      ),
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])]),
  ],
)
"@ | Set-Content -LiteralPath $PyInstallerVersionFile -Encoding Ascii

$PreviousConsoleBuild = $env:LUMINA_CONSOLE_BUILD
$PreviousVersionFile = $env:LUMINA_VERSION_FILE
$env:LUMINA_CONSOLE_BUILD = if ($DiagnosticConsole) { '1' } else { '0' }
try {
    $env:LUMINA_VERSION_FILE = $PyInstallerVersionFile
    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --distpath $PackageOutput `
        --workpath $WorkOutput `
        $Spec
}
finally {
    $env:LUMINA_CONSOLE_BUILD = $PreviousConsoleBuild
    $env:LUMINA_VERSION_FILE = $PreviousVersionFile
}
if ($LASTEXITCODE -ne 0) {
    throw 'Lumina standalone package build failed.'
}

$ReleaseExe = Join-Path $PackageOutput 'Lumina\Lumina.exe'
if (-not (Test-Path -LiteralPath $ReleaseExe -PathType Leaf)) {
    throw 'Standalone package does not contain Lumina.exe.'
}
$ReleaseRoot = Split-Path -Parent $ReleaseExe
foreach ($noticeFile in @('LICENSE', 'NOTICE', 'THIRD_PARTY_NOTICES.md')) {
    Copy-Item `
        -LiteralPath (Join-Path $Root $noticeFile) `
        -Destination (Join-Path $ReleaseRoot $noticeFile) `
        -Force
}

if (-not $SkipInstaller) {
    $Iscc = Find-InnoCompiler
    $IsccArguments = @("/DMyAppVersion=$Version")
    if ($QaBuild) {
        $IsccArguments += '/DQaBuild'
    }
    & $Iscc @IsccArguments $InnoScript
    if ($LASTEXITCODE -ne 0) {
        throw 'Lumina installer build failed.'
    }
}

$InstallerName = if ($QaBuild) {
    "install_Lumina-QA-$Version.exe"
}
else {
    "install_Lumina-$Version.exe"
}
$InstallerPath = Join-Path $InstallerOutput $InstallerName
$GitCommitOutput = & git.exe -C $Root rev-parse HEAD 2>$null
if ($LASTEXITCODE -eq 0 -and $GitCommitOutput) {
    $GitCommit = [string]@($GitCommitOutput)[0]
}
else {
    $GitCommit = $null
}
$Artifacts = @(
    [ordered]@{
        file = 'Lumina/Lumina.exe'
        size = (Get-Item -LiteralPath $ReleaseExe).Length
        sha256 = (Get-FileHash -LiteralPath $ReleaseExe -Algorithm SHA256).Hash
    }
)
if (Test-Path -LiteralPath $InstallerPath) {
    $Artifacts += [ordered]@{
        file = $InstallerName
        size = (Get-Item -LiteralPath $InstallerPath).Length
        sha256 = (Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash
    }
}
$Manifest = [ordered]@{
    version = $Version
    git_commit = $GitCommit
    built_at_utc = [DateTime]::UtcNow.ToString('o')
    platform = 'windows-x64'
    qa_build = [bool]$QaBuild
    artifacts = $Artifacts
}
$Manifest | ConvertTo-Json | Set-Content `
    -LiteralPath (Join-Path $InstallerOutput 'release-manifest.json') `
    -Encoding UTF8

Write-Host ''
Write-Host '[DONE] Lumina Windows release build:'
Write-Host "  Standalone package: $PackageOutput\Lumina"
if (-not $SkipInstaller) {
    Write-Host "  Installer: $InstallerPath"
}
