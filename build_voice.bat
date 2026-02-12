@echo off
REM Quick build script for AGENT_GURU Voice

echo ╔════════════════════════════════════════════════════════════╗
echo ║     AGENT_GURU Voice Builder                               ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

echo 🔨 Building voice-enabled binary...
echo.

cargo build --release --bin agent_guru_voice

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Build failed!
    echo    Check errors above
    pause
    exit /b 1
)

echo.
echo ✅ Build successful!
echo.
echo 📦 Binary location: target\release\agent_guru_voice.exe
echo.
echo Next steps:
echo   1. Run: scripts\create_windows_installer.bat
echo   2. Or test directly: target\release\agent_guru_voice.exe
echo.
pause
