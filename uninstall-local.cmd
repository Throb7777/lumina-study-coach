@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "NO_PAUSE="
for %%A in (%*) do if /I "%%~A"=="-NonInteractive" set "NO_PAUSE=1"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\uninstall-study-web.ps1" %*
if errorlevel 1 (
  echo.
  echo [Lumina] 卸载未完成，请查看上方错误。学习数据不会因失败被继续清理。
  if not defined NO_PAUSE pause
  exit /b 1
)

echo.
echo [Lumina] 卸载流程已完成。
if not defined NO_PAUSE pause
