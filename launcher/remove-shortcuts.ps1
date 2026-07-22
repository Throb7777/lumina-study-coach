param(
    [switch]$LegacyOnly,
    [switch]$Quiet
)

$ErrorActionPreference = 'Stop'
$Desktop = [Environment]::GetFolderPath('Desktop')
$Programs = [Environment]::GetFolderPath('Programs')
$LegacyDesktopShortcut = Join-Path $Desktop '学习流程教练.lnk'
$LegacyStartMenuFolder = Join-Path $Programs '学习流程教练'

Remove-Item -LiteralPath $LegacyDesktopShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $LegacyStartMenuFolder -Recurse -Force -ErrorAction SilentlyContinue

if (-not $LegacyOnly) {
    Remove-Item -LiteralPath (Join-Path $Desktop 'Lumina.lnk') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $Programs 'Lumina') -Recurse -Force -ErrorAction SilentlyContinue
}

if (-not $Quiet) {
    if ($LegacyOnly) {
        Write-Host '已清理旧版“学习流程教练”快捷方式。'
    }
    else {
        Write-Host '已删除 Lumina 快捷方式。本地学习数据和项目源码未被删除。'
    }
}
