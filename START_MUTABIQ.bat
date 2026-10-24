@echo off
rem ===== Mutabiq one-click launcher for Windows =====
rem Double-click this file. First run installs everything (15-30 min); later runs start in seconds.
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Mutabiq launcher

echo.
echo  ==========================================
echo    Mutabiq - compliance map for Jordan
echo  ==========================================
echo.

rem ---- 1. Real Python 3.11+ (ignores the Microsoft Store "python" shortcut) ----
call :findpython
if not defined PY (
  echo [1/4] Python 3.11+ not found. Installing Python 3.12 with winget...
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  call :findpython
)
if not defined PY (
  echo.
  echo  Python could not be found after installing. CLOSE this window and double-click START_MUTABIQ.bat again.
  pause
  exit /b
)
echo [1/4] Python found: !PY!

rem ---- 2. Ollama (runs the open-source AI model locally) ----
set "OLLAMA=ollama"
where ollama >nul 2>nul
if errorlevel 1 if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
"!OLLAMA!" --version >nul 2>nul
if errorlevel 1 (
  echo [2/4] Ollama is not installed. Installing it with winget...
  winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements
  set "OLLAMA=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
)
echo [2/4] Ollama found.

rem ---- 3. First-time setup ----
if not exist ".venv\Scripts\python.exe" (
  echo [3/4] First run: installing packages, AI models, law texts. This takes 15-30 minutes...
  powershell -ExecutionPolicy Bypass -File setup.ps1 -Py "!PY!" -Ollama "!OLLAMA!"
  if errorlevel 1 (
    echo.
    echo  Setup stopped with an error. Take a photo of this window and send it to Claude.
    pause
    exit /b
  )
) else (
  echo [3/4] Already set up.
  if not exist "db\mutabiq.db" .venv\Scripts\python.exe scripts\seed.py
)

rem ---- 4. Start the demo site and the app ----
echo [4/4] Starting the demo site and the Mutabiq app...
start "Mutabiq demo site (keep open)" cmd /k ".venv\Scripts\python.exe demo_site\app.py"
start "Mutabiq app (keep open)" cmd /k ".venv\Scripts\python.exe -m streamlit run app.py --server.headless true --server.address localhost --browser.gatherUsageStats false"
timeout /t 10 /nobreak >nul
start "" http://localhost:8501

echo.
echo  Mutabiq is running at  http://localhost:8501
echo  Log in:  shifa / shifa123   (client)     admin / admin123   (admin)
echo  Scan the domain  127.0.0.1  to scan the demo site.
echo.
echo  To stop: close the two black windows titled "Mutabiq".
echo.
pause
exit /b

rem ---- helper: set PY to the full path of a real Python >= 3.11 ----
:findpython
set "PY="
for %%C in ("py -3.12" "py -3" "python") do (
  if not defined PY (
    for /f "usebackq delims=" %%P in (`%%~C -c "import sys; print(sys.executable if sys.version_info >= (3,11) else '')" 2^>nul`) do (
      if not "%%P"=="" set "PY=%%P"
    )
  )
)
if not defined PY for %%D in (Python313 Python312 Python311) do (
  if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\%%D\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\%%D\python.exe"
)
exit /b
