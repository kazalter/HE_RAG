@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_BIN="
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" --version >nul 2>nul
  if not errorlevel 1 set "PYTHON_BIN=.venv\Scripts\python.exe"
)

if not defined PYTHON_BIN (
  python --version >nul 2>nul
  if not errorlevel 1 set "PYTHON_BIN=python"
)

if not defined PYTHON_BIN (
  py --version >nul 2>nul
  if not errorlevel 1 set "PYTHON_BIN=py"
)

if not defined PYTHON_BIN (
  echo No usable Python was found. Please install Python or recreate .venv.
  goto fail
)

echo Running one-click RAG pipeline...
"%PYTHON_BIN%" -m src.pipeline %*
if errorlevel 1 goto fail
goto end

:fail
echo RAG pipeline failed. Please check the error message above.
pause

:end
pause
endlocal
