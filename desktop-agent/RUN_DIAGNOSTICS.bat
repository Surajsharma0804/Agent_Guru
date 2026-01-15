@echo off
REM GURU System Diagnostics Launcher
REM
REM This batch file runs comprehensive system diagnostics to verify
REM all GURU components are functioning correctly.
REM
REM Requirements validated: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6

echo ========================================================================
echo GURU SYSTEM DIAGNOSTICS
echo ========================================================================
echo.
echo Running comprehensive system diagnostics...
echo This will test all critical components.
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause >nul

cd /d "%~dp0"

python run_diagnostics.py

echo.
echo ========================================================================
echo Diagnostics complete.
echo ========================================================================
echo.
pause
