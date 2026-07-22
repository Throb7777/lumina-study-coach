@echo off
setlocal
cd /d "%~dp0"

set "STUDY_WEB_DESKTOP_LAUNCH=1"

set "ALL_PROXY="
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "NO_PROXY="

for /f "tokens=2,*" %%A in ('reg query HKCU\Environment /v ALL_PROXY 2^>nul ^| find "REG_"') do set "ALL_PROXY=%%B"
for /f "tokens=2,*" %%A in ('reg query HKCU\Environment /v HTTP_PROXY 2^>nul ^| find "REG_"') do set "HTTP_PROXY=%%B"
for /f "tokens=2,*" %%A in ('reg query HKCU\Environment /v HTTPS_PROXY 2^>nul ^| find "REG_"') do set "HTTPS_PROXY=%%B"
for /f "tokens=2,*" %%A in ('reg query HKCU\Environment /v NO_PROXY 2^>nul ^| find "REG_"') do set "NO_PROXY=%%B"

if not exist "backend\.venv\Scripts\python.exe" (
  echo [Lumina] Backend environment is missing.
  echo Run: cd backend ^&^& uv sync --locked
  pause
  exit /b 1
)

if not exist "frontend\dist\index.html" (
  echo [Lumina] Frontend build is missing.
  echo Run: cd frontend ^&^& npm run build
  pause
  exit /b 1
)

echo [Lumina] Diagnostic startup on http://127.0.0.1:8000/courses
echo Daily use should start from the desktop shortcut. Keep this window open for diagnostics.
echo Press Ctrl+C to stop the service.
echo.

start "" /b powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8000/courses'"

cd backend
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

if errorlevel 1 (
  echo.
  echo [Lumina] The service stopped with an error.
  pause
)
