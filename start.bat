@echo off
rem Double-click to run NutriLens. Sets itself up on first run, then opens http://localhost:8000
setlocal
title NutriLens
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
  echo Setting up the Python environment ^(first run only^)...
  python -m venv .venv || goto :error
  ".venv\Scripts\python" -m pip install -q -r requirements.txt || goto :error
)

if not exist "%~dp0frontend\dist\index.html" (
  echo Building the interface ^(first run only^)...
  pushd "%~dp0frontend"
  call npm install || goto :error
  call npm run build || goto :error
  popd
)

rem Photo analysis needs the Ollama AI service; start it if it isn't already running.
tasklist /fi "imagename eq ollama.exe" | find /i "ollama.exe" >nul || (
  if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
)

echo.
echo   NutriLens is running at http://localhost:8000
echo   Keep this window open while you use the app. Close it to stop NutriLens.
echo.
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8000"
".venv\Scripts\python" -m uvicorn app.main:app --port 8000
goto :eof

:error
echo.
echo Setup failed. See the messages above.
pause
