@echo off
REM GURU Fresh Start Script
REM This script starts GURU with a clean slate for testing

echo ================================================================================
echo GURU AI ASSISTANT - FRESH START
echo ================================================================================
echo.
echo This will start GURU with full debug logging enabled.
echo.
echo IMPORTANT:
echo - Make sure your microphone is connected and working
echo - Make sure your speakers are connected and working
echo - Windows Hello should be configured if you want biometric auth
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause >nul

echo.
echo Starting GURU...
echo.

cd /d "%~dp0"
python launch_guru_complete.py

pause
