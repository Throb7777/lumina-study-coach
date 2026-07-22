@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\install-study-web.ps1" %*
if errorlevel 1 (
  echo.
  echo [Lumina] 安装或修复未完成，请查看上方错误。
  pause
  exit /b 1
)

echo.
echo [Lumina] 安装或修复已完成。
powershell.exe -NoProfile -Command "Start-Sleep -Seconds 3"
