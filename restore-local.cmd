@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launcher\restore-study-web.ps1" %*
if errorlevel 1 (
  echo.
  echo [Lumina] 恢复未完成，请查看上方错误。当前数据不会因失败被继续替换。
  pause
  exit /b 1
)

echo.
echo [Lumina] 恢复流程已结束。
pause
