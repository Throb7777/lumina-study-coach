@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\build-release.ps1" %*
if errorlevel 1 (
  echo.
  echo [Lumina] Windows 发布构建失败，请查看上方错误。
  pause
  exit /b 1
)

echo.
echo [Lumina] Windows 发布构建完成。
pause
