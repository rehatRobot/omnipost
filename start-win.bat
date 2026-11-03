@echo off
setlocal
cd /d "%~dp0"
TITLE OmniPost Local Servers

if not exist ".venv\Scripts\python.exe" goto missing_setup
if not exist "conf.py" goto missing_setup
if not exist "sau_frontend\node_modules\.bin\vite.cmd" goto missing_setup
where npm.cmd >nul 2>nul
if errorlevel 1 goto missing_setup
set "PATH=%~dp0.venv\Scripts;%PATH%"
set "PYTHONIOENCODING=utf-8"
python -c "import flask, flask_cors, xhs, patchright.async_api, playwright.async_api, PIL, cv2, loguru, qrcode, segno"
if errorlevel 1 goto missing_setup
python db\createTable.py
if errorlevel 1 goto init_failed

START "OmniPost Backend" cmd /k "python -u sau_backend.py"
START "OmniPost Frontend" /D "%~dp0sau_frontend" cmd /k "npm run dev -- --host 127.0.0.1 --strictPort"
echo Open http://127.0.0.1:5173/
echo Close BOTH server windows to stop the services.
exit /b 0

:missing_setup
echo First complete the installation steps in README.md:
echo   Copy conf.example.py to conf.py if it does not exist.
echo   uv sync --locked --extra web --python 3.12
echo   uv run --no-sync playwright install chromium
echo   npm --prefix sau_frontend ci
pause
exit /b 1

:init_failed
echo Database initialization failed. See the error above.
pause
exit /b 1
