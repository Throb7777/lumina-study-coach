[CmdletBinding()]
param(
    [string]$Archive,
    [switch]$NonInteractive,
    [switch]$ConfirmRestore
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$RuntimeData = Join-Path $Root 'runtime-data'
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
$ArchiveScript = Join-Path $PSScriptRoot 'data_archive.py'
$HealthUrl = 'http://127.0.0.1:8000/api/health'

$ServiceRunning = $false
try {
    Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 2 | Out-Null
    $ServiceRunning = $true
}
catch {
    $ServiceRunning = $false
}
if ($ServiceRunning) {
    throw 'Lumina 仍在运行。请先关闭 Lumina，再执行恢复。'
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw '未找到 Lumina Python 环境，请先运行 install-local.cmd。'
}
if ([string]::IsNullOrWhiteSpace($Archive)) {
    if ($NonInteractive) { throw '非交互恢复必须通过 -Archive 指定归档文件。' }
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Filter = 'Lumina 备份归档 (lumina-backup-*.zip)|lumina-backup-*.zip|ZIP 文件 (*.zip)|*.zip'
    $dialog.Title = '选择 Lumina 学习数据归档'
    if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
        Write-Host '已取消恢复。'
        exit 0
    }
    $Archive = $dialog.FileName
}
$Archive = [IO.Path]::GetFullPath($Archive)
if (-not (Test-Path -LiteralPath $Archive -PathType Leaf)) {
    throw "归档文件不存在：$Archive"
}

& $Python $ArchiveScript inspect --archive $Archive | Out-Null
if ($LASTEXITCODE -ne 0) { throw '归档校验失败，未修改当前数据。' }

if (-not $ConfirmRestore) {
    if ($NonInteractive) { throw '非交互恢复必须同时传入 -ConfirmRestore。' }
    Write-Host '恢复会用归档中的数据库和材料替换当前学习数据；日志和登录状态会保留。'
    $confirmation = Read-Host '请输入 RESTORE 继续'
    if ($confirmation -cne 'RESTORE') {
        Write-Host '已取消恢复，当前数据未修改。'
        exit 0
    }
}

& $Python $ArchiveScript restore `
    --archive $Archive `
    --runtime-data $RuntimeData `
    --replace `
    --confirm RESTORE | Out-Null
if ($LASTEXITCODE -ne 0) { throw '恢复失败；现有数据已保留或回滚。' }
Write-Host '[完成] 数据库和材料已恢复。现在可以重新启动 Lumina。'
