@echo off
setlocal
cd /d "%~dp0"

if not exist "frontend\dist\index.html" (
  echo Building Vue frontend...
  cd frontend
  if not exist "node_modules" (
    call npm.cmd install
    if errorlevel 1 goto fail
  )
  call npm.cmd run build
  if errorlevel 1 goto fail
  cd ..
)

echo Starting FastAPI backend...
python -m src.launcher
goto end

:fail
echo Failed to start web app.
cd /d "%~dp0"
pause

:end
pause
endlocal
