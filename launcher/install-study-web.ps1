param(
    [switch]$SkipLaunch,
    [switch]$SkipShortcuts,
    [switch]$NoInstallPrerequisites
)

$ErrorActionPreference = 'Stop'
$Root = (Split-Path -Parent $PSScriptRoot)
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$RuntimeData = Join-Path $Root 'runtime-data'
$Database = Join-Path $RuntimeData 'learning-flow-coach.db'
$Materials = Join-Path $RuntimeData 'materials'
$ArchiveScript = Join-Path $PSScriptRoot 'data_archive.py'
$FirstRunMarker = Join-Path $RuntimeData 'first-run.pending'
$IconPath = Join-Path $PSScriptRoot 'assets\lumina.ico'
$UninstallCommand = Join-Path $Root 'uninstall-local.cmd'

if (-not (Test-Path -LiteralPath $IconPath -PathType Leaf)) {
    throw "Lumina 自定义图标缺失：$IconPath。安装已停止，不会创建通用图标快捷方式。"
}

function Refresh-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath"
}

function Refresh-UserProxyEnvironment {
    foreach ($name in @('ALL_PROXY', 'HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY')) {
        Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
        $value = [Environment]::GetEnvironmentVariable($name, 'User')
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            Set-Item -Path "Env:$name" -Value $value
        }
    }
}

function Install-Prerequisite([string]$Name, [string]$WingetId) {
    if ($NoInstallPrerequisites) {
        throw "未检测到 $Name。请安装后重新运行 install-local.cmd。"
    }
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw "未检测到 $Name，且当前系统没有 WinGet。请手动安装 $Name 后重试。"
    }
    $choice = Read-Host "未检测到 $Name，是否使用 WinGet 安装？[Y/N]"
    if ($choice -notin @('Y', 'y')) {
        throw "已取消安装 $Name。"
    }
    & winget.exe install --id $WingetId --exact --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "$Name 安装失败，WinGet 退出码：$LASTEXITCODE"
    }
    Refresh-ProcessPath
}

function Prepare-OptionalOcr {
    $tesseractCommand = Get-Command tesseract.exe -ErrorAction SilentlyContinue
    $tesseractPath = if ($tesseractCommand) { $tesseractCommand.Source } else { $null }
    if (-not $tesseractPath) {
        $candidate = Join-Path $env:ProgramFiles 'Tesseract-OCR\tesseract.exe'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $tesseractPath = $candidate
        }
    }
    if (-not $tesseractPath) {
        Write-Warning '未检测到可选的 Tesseract OCR。普通 PDF 不受影响；扫描 PDF 会保留为可重试状态。'
        if ($NoInstallPrerequisites) { return }
        if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
            Write-Warning '当前系统没有 WinGet，已跳过可选 OCR 安装。'
            return
        }
        $installChoice = Read-Host '是否安装 Tesseract OCR 以支持扫描 PDF？[Y/N]'
        if ($installChoice -notmatch '^[Yy]$') { return }
        & winget.exe install --id tesseract-ocr.tesseract --exact --source winget --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Tesseract 安装失败，退出码：$LASTEXITCODE。其余 Lumina 功能不受影响。"
            return
        }
        Refresh-ProcessPath
        $tesseractCommand = Get-Command tesseract.exe -ErrorAction SilentlyContinue
        $tesseractPath = if ($tesseractCommand) { $tesseractCommand.Source } else { $null }
        if (-not $tesseractPath) {
            $candidate = Join-Path $env:ProgramFiles 'Tesseract-OCR\tesseract.exe'
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                $tesseractPath = $candidate
            }
        }
    }
    if (-not $tesseractPath) { return }
    $languages = & $tesseractPath --list-langs 2>$null
    if ($languages -contains 'chi_sim' -and $languages -contains 'eng') {
        Write-Host '[通过] Tesseract 中文与英文语言包可用。'
        return
    }
    if ($NoInstallPrerequisites) {
        Write-Warning 'Tesseract 缺少 chi_sim 或 eng 语言包，扫描 PDF 中文识别暂不可用。'
        return
    }
    $languageChoice = Read-Host 'Tesseract 缺少中文语言包，是否从官方 tessdata_fast 下载约 2.5 MB？[Y/N]'
    if ($languageChoice -notmatch '^[Yy]$') { return }
    $target = Join-Path $RuntimeData 'ocr\tessdata'
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    $systemTessdata = Join-Path (Split-Path -Parent $tesseractPath) 'tessdata'
    $temporaryLanguage = Join-Path $target 'chi_sim.traineddata.download'
    try {
        Copy-Item -LiteralPath (Join-Path $systemTessdata 'eng.traineddata') -Destination $target -Force
        $languageUrl = 'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/chi_sim.traineddata'
        Invoke-WebRequest -Uri $languageUrl -OutFile $temporaryLanguage
        Move-Item -LiteralPath $temporaryLanguage -Destination (Join-Path $target 'chi_sim.traineddata') -Force
        Write-Host '[通过] 扫描 PDF 的中文与英文 OCR 语言包已准备。'
    }
    catch {
        Remove-Item -LiteralPath $temporaryLanguage -Force -ErrorAction SilentlyContinue
        Write-Warning "OCR 语言包准备失败：$($_.Exception.Message)。其余 Lumina 功能不受影响，可稍后重新运行安装/修复。"
    }
}

function Require-Command([string]$Command, [string]$Name, [string]$WingetId) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        Install-Prerequisite $Name $WingetId
    }
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "已经安装 $Name，但当前进程仍无法找到 $Command。请关闭窗口后重新运行安装。"
    }
}

function Require-MinimumVersion(
    [string]$Label,
    [string]$RawVersion,
    [version]$Minimum
) {
    $versionMatch = [regex]::Match($RawVersion, '\d+(?:\.\d+){1,3}')
    if (-not $versionMatch.Success) {
        throw "无法识别 $Label 版本：$RawVersion"
    }
    try {
        $actual = [version]$versionMatch.Value
    }
    catch {
        throw "无法识别 $Label 版本：$RawVersion"
    }
    if ($actual -lt $Minimum) {
        throw "$Label 版本过低：$actual，需要 $Minimum 或更高版本。"
    }
    Write-Host "[通过] $Label $actual"
}

function New-Shortcut(
    [string]$ShortcutPath,
    [string]$TargetPath,
    [string]$Arguments,
    [string]$Description
) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $TargetPath
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $Root
    $shortcut.Description = $Description
    $shortcut.WindowStyle = 7
    $shortcut.IconLocation = "$IconPath,0"
    $shortcut.Save()
}

Write-Host 'Lumina - 首次安装 / 修复'
Write-Host '项目标识：lumina-study-coach'
Write-Host "项目目录：$Root"
Write-Host ''

Refresh-ProcessPath
Refresh-UserProxyEnvironment
Require-Command 'uv.exe' 'uv' 'astral-sh.uv'
Require-Command 'node.exe' 'Node.js LTS' 'OpenJS.NodeJS.LTS'
Require-Command 'npm.cmd' 'npm' 'OpenJS.NodeJS.LTS'

Require-MinimumVersion 'uv' (& uv.exe --version | Select-Object -Last 1).Replace('uv ', '') ([version]'0.11.0')
Require-MinimumVersion 'Node.js' (& node.exe --version | Select-Object -Last 1) ([version]'22.12.0')
Require-MinimumVersion 'npm' (& npm.cmd --version | Select-Object -Last 1) ([version]'11.0.0')
Prepare-OptionalOcr

Write-Host ''
Write-Host '[1/3] 准备 Python 3.12 和后端依赖...'
$VenvPython = Join-Path $Backend '.venv\Scripts\python.exe'
$PythonSelector = $null
if (Test-Path -LiteralPath $VenvPython -PathType Leaf) {
    $venvVersion = & $VenvPython -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sys.version_info.micro, sep=chr(46))'
    if ($LASTEXITCODE -eq 0 -and $venvVersion -match '^3\.12\.') {
        $PythonSelector = $VenvPython
        Write-Host "[通过] 复用现有 Python $venvVersion 虚拟环境。"
    }
}
if (-not $PythonSelector) {
    $systemPython = & uv.exe python find 3.12 --system 2>$null
    if ($LASTEXITCODE -eq 0 -and $systemPython) {
        $PythonSelector = ($systemPython | Select-Object -Last 1).Trim()
        Write-Host "[通过] 使用系统 Python 3.12：$PythonSelector"
    }
}
if (-not $PythonSelector) {
    & uv.exe python install 3.12
    if ($LASTEXITCODE -ne 0) { throw "Python 3.12 准备失败，退出码：$LASTEXITCODE" }
    $PythonSelector = '3.12'
}
Push-Location $Backend
try {
    & uv.exe sync --locked --python $PythonSelector
    if ($LASTEXITCODE -ne 0) { throw "后端依赖安装失败，退出码：$LASTEXITCODE" }
    $SyncedPython = Join-Path $Backend '.venv\Scripts\python.exe'
    & $SyncedPython $ArchiveScript create `
        --database $Database `
        --materials $Materials `
        --destination (Join-Path $RuntimeData 'backups')
    if ($LASTEXITCODE -ne 0) { throw "本地数据归档失败，退出码：$LASTEXITCODE" }
}
finally {
    Pop-Location
}

Write-Host ''
Write-Host '[2/3] 安装前端依赖并生成生产构建...'
Push-Location $Frontend
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw "前端依赖安装失败，退出码：$LASTEXITCODE" }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "前端构建失败，退出码：$LASTEXITCODE" }
}
finally {
    Pop-Location
}

$Pythonw = Join-Path $Backend '.venv\Scripts\pythonw.exe'
$StartScript = Join-Path $PSScriptRoot 'start-study-web.pyw'
$StopScript = Join-Path $PSScriptRoot 'stop-study-web.pyw'
if (-not (Test-Path -LiteralPath $Pythonw -PathType Leaf)) {
    throw "未找到无窗口 Python 运行器：$Pythonw"
}
if (-not (Test-Path -LiteralPath $UninstallCommand -PathType Leaf)) {
    throw "未找到 Lumina 卸载入口：$UninstallCommand"
}

New-Item -ItemType Directory -Path $RuntimeData -Force | Out-Null
if (-not (Test-Path -LiteralPath $Database) -and -not (Test-Path -LiteralPath $FirstRunMarker)) {
    Set-Content -LiteralPath $FirstRunMarker -Value 'pending' -Encoding ASCII
}

Write-Host ''
Write-Host '[3/3] 配置本机启动入口...'
if (-not $SkipShortcuts) {
    $Desktop = [Environment]::GetFolderPath('Desktop')
    $Programs = [Environment]::GetFolderPath('Programs')
    $StartMenuFolder = Join-Path $Programs 'Lumina'
    & (Join-Path $PSScriptRoot 'remove-shortcuts.ps1') -Quiet
    New-Item -ItemType Directory -Path $StartMenuFolder -Force | Out-Null

    New-Shortcut `
        (Join-Path $Desktop 'Lumina.lnk') `
        $Pythonw `
        ('"' + $StartScript + '"') `
        '启动 Lumina'
    New-Shortcut `
        (Join-Path $StartMenuFolder 'Lumina.lnk') `
        $Pythonw `
        ('"' + $StartScript + '"') `
        '启动 Lumina'
    New-Shortcut `
        (Join-Path $StartMenuFolder '停止 Lumina.lnk') `
        $Pythonw `
        ('"' + $StopScript + '"') `
        '安全停止 Lumina 本地服务'
    New-Shortcut `
        (Join-Path $StartMenuFolder '卸载 Lumina.lnk') `
        (Join-Path $env:SystemRoot 'System32\cmd.exe') `
        ('/c ""' + $UninstallCommand + '""') `
        '卸载 Lumina；默认保留学习数据'
    Write-Host '[通过] 已创建 Lumina 桌面入口，以及开始菜单中的启动、停止和卸载入口。'
}
else {
    Write-Host '[跳过] 未创建快捷方式。'
}

if (-not $SkipLaunch) {
    Start-Process -FilePath $Pythonw -ArgumentList ('"' + $StartScript + '"') -WorkingDirectory $Root
    Write-Host '[完成] 正在打开 Lumina。'
}
else {
    Write-Host '[完成] 已跳过自动启动。'
}
