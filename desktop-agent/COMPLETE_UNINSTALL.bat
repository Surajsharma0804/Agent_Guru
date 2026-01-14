@echo off
REM GURU Complete Uninstall Script
REM This removes ALL GURU data and configuration

echo ================================================================================
echo GURU COMPLETE UNINSTALL
echo ================================================================================
echo.
echo WARNING: This will DELETE ALL GURU data including:
echo   - User profiles and passwords
echo   - Configuration files
echo   - Audit logs
echo   - All settings
echo.
echo Press Ctrl+C to cancel or any key to continue...
pause >nul

echo.
echo [1/5] Terminating all GURU processes...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq GURU*" 2>nul
taskkill /F /IM pythonw.exe /FI "WINDOWTITLE eq GURU*" 2>nul
echo Done.

echo.
echo [2/5] Removing configuration files...
if exist "%USERPROFILE%\.guru" (
    rmdir /S /Q "%USERPROFILE%\.guru"
    echo Removed: %USERPROFILE%\.guru
)
if exist ".kiro" (
    rmdir /S /Q ".kiro"
    echo Removed: .kiro
)
echo Done.

echo.
echo [3/5] Removing audit logs...
if exist "audit_logs" (
    rmdir /S /Q "audit_logs"
    echo Removed: audit_logs
)
if exist "logs" (
    rmdir /S /Q "logs"
    echo Removed: logs
)
echo Done.

echo.
echo [4/5] Removing cached data...
if exist "__pycache__" (
    rmdir /S /Q "__pycache__"
)
if exist "src\__pycache__" (
    rmdir /S /Q "src\__pycache__"
)
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /S /Q "%%d"
for /d /r . %%d in (*.egg-info) do @if exist "%%d" rmdir /S /Q "%%d"
echo Done.

echo.
echo [5/5] Removing temporary files...
if exist "*.pyc" del /S /Q "*.pyc" 2>nul
if exist "*.pyo" del /S /Q "*.pyo" 2>nul
if exist ".pytest_cache" rmdir /S /Q ".pytest_cache"
if exist ".hypothesis" rmdir /S /Q ".hypothesis"
echo Done.

echo.
echo ================================================================================
echo UNINSTALL COMPLETE
echo ================================================================================
echo.
echo GURU has been completely removed from your system.
echo.
echo To reinstall:
echo   1. Run: python launch_guru_complete.py
echo   2. Complete the setup wizard
echo.
pause
