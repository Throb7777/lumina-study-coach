[CmdletBinding()]
param(
    [ValidateSet('KeepData', 'CleanGenerated', 'CleanAll')]
    [string]$Mode = 'KeepData',
    [switch]$NonInteractive,
    [switch]$ConfirmDataRemoval,
    [switch]$ConfirmPermanentRemoval,
    [switch]$Backup,
    [switch]$NoBackup,
    [string]$BackupDirectory,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$Root = (Split-Path -Parent $PSScriptRoot)
$RuntimeData = Join-Path $Root 'runtime-data'
$Database = Join-Path $RuntimeData 'learning-flow-coach.db'
$Materials = Join-Path $RuntimeData 'materials'
$PolicyScript = Join-Path $PSScriptRoot 'uninstall_policy.py'
$ArchiveScript = Join-Path $PSScriptRoot 'data_archive.py'
$RemoveShortcutsScript = Join-Path $PSScriptRoot 'remove-shortcuts.ps1'
$VenvPython = Join-Path $Root 'backend\.venv\Scripts\python.exe'
$ServiceHealthUrl = 'http://127.0.0.1:8000/api/health'
$ShutdownUrl = 'http://127.0.0.1:8000/api/system/shutdown'
$AllowedTargets = @(
    [IO.Path]::GetFullPath((Join-Path $Root 'backend\.venv')),
    [IO.Path]::GetFullPath((Join-Path $Root 'frontend\node_modules')),
    [IO.Path]::GetFullPath((Join-Path $Root 'frontend\dist')),
    [IO.Path]::GetFullPath($RuntimeData)
)

function Read-UninstallMode {
    Write-Host ''
    Write-Host '请选择卸载范围：'
    Write-Host '  1. 仅移除 Lumina 入口（默认，保留全部学习数据和运行环境）'
    Write-Host '  2. 同时清理生成环境（保留学习数据）'
    Write-Host '  3. 同时清理生成环境和本地学习数据'
    $choice = Read-Host '输入 1、2 或 3，直接回车选择 1'
    switch ($choice) {
        '2' { return 'CleanGenerated' }
        '3' { return 'CleanAll' }
        default { return 'KeepData' }
    }
}

function Test-LuminaService {
    try {
        $health = Invoke-RestMethod -Uri $ServiceHealthUrl -Method Get -TimeoutSec 2
        return $health.status -eq 'ok' -and $health.service -eq 'learning-flow-coach-api'
    }
    catch {
        return $false
    }
}

function Stop-LuminaService {
    if (-not (Test-LuminaService)) {
        Write-Host '[通过] Lumina 本地服务当前未运行。'
        return
    }
    Write-Host '[进行中] 正在安全停止 Lumina 本地服务...'
    try {
        Invoke-RestMethod `
            -Uri $ShutdownUrl `
            -Method Post `
            -ContentType 'application/json' `
            -Body '{"confirm":true}' `
            -TimeoutSec 5 | Out-Null
    }
    catch {
        throw '无法安全停止 Lumina。服务可能由诊断终端启动，请先在对应终端中停止，再重新卸载。'
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 250
        if (-not (Test-LuminaService)) {
            Write-Host '[通过] Lumina 本地服务已停止。'
            return
        }
    }
    throw 'Lumina 本地服务未能在 15 秒内停止，未执行清理。'
}

function Resolve-BackupPython {
    if (Test-Path -LiteralPath $VenvPython -PathType Leaf) {
        return $VenvPython
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }
    throw '无法创建最后备份：未找到 Python。学习数据尚未删除。'
}

function Remove-AllowlistedTarget([string]$Target) {
    $fullTarget = [IO.Path]::GetFullPath($Target)
    if ($AllowedTargets -notcontains $fullTarget) {
        throw "拒绝删除未列入固定清单的路径：$fullTarget"
    }
    if (Test-Path -LiteralPath $fullTarget) {
        Remove-Item -LiteralPath $fullTarget -Recurse -Force
        Write-Host "[已清理] $fullTarget"
    }
    else {
        Write-Host "[跳过] 路径不存在：$fullTarget"
    }
}

if ($Backup -and $NoBackup) {
    throw '-Backup 与 -NoBackup 不能同时使用。'
}
if (-not $NonInteractive -and -not $PSBoundParameters.ContainsKey('Mode')) {
    $Mode = Read-UninstallMode
}

if ($Mode -eq 'CleanAll') {
    if ($NonInteractive) {
        if (-not ($ConfirmDataRemoval -and $ConfirmPermanentRemoval)) {
            throw '非交互清理本地数据必须同时提供 -ConfirmDataRemoval 和 -ConfirmPermanentRemoval。'
        }
    }
    else {
        $firstConfirmation = Read-Host '将永久删除课程、记录、材料缓存、设置和日志。输入 DELETE 继续'
        if ($firstConfirmation -cne 'DELETE') {
            Write-Host '已取消卸载，未删除任何内容。'
            exit 0
        }
        $secondConfirmation = Read-Host '再次确认：输入 DELETE LUMINA DATA'
        if ($secondConfirmation -cne 'DELETE LUMINA DATA') {
            Write-Host '已取消卸载，未删除任何内容。'
            exit 0
        }
    }
}

$targets = @()
if ($Mode -in @('CleanGenerated', 'CleanAll')) {
    $targets += Join-Path $Root 'backend\.venv'
    $targets += Join-Path $Root 'frontend\node_modules'
    $targets += Join-Path $Root 'frontend\dist'
}
if ($Mode -eq 'CleanAll') {
    $targets += $RuntimeData
}

Write-Host 'Lumina 源码型卸载'
Write-Host '项目标识：lumina-study-coach'
Write-Host "卸载模式：$Mode"
Write-Host '项目源码和 Obsidian Vault 永远不在清理清单中。'

if ($DryRun) {
    Write-Host '[预演] 不停止服务、不备份、不删除快捷方式或文件。'
    foreach ($target in $targets) {
        $fullTarget = [IO.Path]::GetFullPath($target)
        if ($AllowedTargets -notcontains $fullTarget) {
            throw "预演发现未列入固定清单的路径：$fullTarget"
        }
        Write-Host "[计划清理] $fullTarget"
    }
    exit 0
}

Stop-LuminaService

$shouldBackup = $Backup
if ($Mode -eq 'CleanAll' -and -not $Backup -and -not $NoBackup) {
    if ($NonInteractive) {
        $shouldBackup = $true
    }
    else {
        $backupChoice = Read-Host '是否在文档目录创建最后一份完整学习数据归档？[Y/n]'
        $shouldBackup = $backupChoice -notin @('N', 'n')
    }
}

if ($shouldBackup -and (Test-Path -LiteralPath $Database -PathType Leaf)) {
    if ([string]::IsNullOrWhiteSpace($BackupDirectory)) {
        $BackupDirectory = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Lumina Backups'
    }
    $backupRoot = [IO.Path]::GetFullPath($BackupDirectory)
    $runtimeRoot = [IO.Path]::GetFullPath($RuntimeData).TrimEnd('\') + '\'
    if (($backupRoot.TrimEnd('\') + '\').StartsWith($runtimeRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw '最后备份目录不能位于 runtime-data 内，因为该目录可能在卸载时被清理。'
    }
    $python = Resolve-BackupPython
    $backupPath = & $python $ArchiveScript create `
        --database $Database `
        --materials $Materials `
        --destination $backupRoot
    if ($LASTEXITCODE -ne 0) {
        throw '最后学习数据归档失败，未执行清理。'
    }
    Write-Host "[通过] 最后学习数据归档：$backupPath"
}
elseif ($shouldBackup) {
    Write-Host '[跳过] 当前没有本地数据库，无需创建最后归档。'
}

foreach ($target in $targets) {
    Remove-AllowlistedTarget $target
}

& $RemoveShortcutsScript -Quiet
Write-Host ''
switch ($Mode) {
    'KeepData' {
        Write-Host '[完成] 已移除 Lumina 启动入口，学习数据、运行环境和项目源码均已保留。'
    }
    'CleanGenerated' {
        Write-Host '[完成] 已移除 Lumina 入口和生成环境；学习数据与项目源码已保留。'
    }
    'CleanAll' {
        Write-Host '[完成] 已移除 Lumina 入口、生成环境和本地学习数据；项目源码与 Obsidian Vault 未被触碰。'
    }
}
