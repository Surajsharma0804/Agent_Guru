@echo off
REM AGENT_GURU Whisper.cpp Setup Script for Windows
REM This script helps set up Whisper for production-grade speech recognition

echo ========================================
echo AGENT_GURU Whisper Setup
echo ========================================
echo.

REM Check if models directory exists
if not exist "models\whisper" (
    echo Creating models directory...
    mkdir models\whisper
)

REM Check if model already exists
if exist "models\whisper\ggml-base.bin" (
    echo ✅ Whisper model already exists
    goto :build
)

echo 📥 Downloading Whisper base model...
echo This may take a few minutes (142 MB)
echo.

REM Download using PowerShell
powershell -Command "& {Invoke-WebRequest -Uri 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin' -OutFile 'models\whisper\ggml-base.bin'}"

if %ERRORLEVEL% NEQ 0 (
    echo ❌ Download failed
    echo Please download manually from:
    echo https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin
    echo And place in: models\whisper\
    pause
    exit /b 1
)

echo ✅ Model downloaded successfully

:build
echo.
echo ========================================
echo Building with Whisper support
echo ========================================
echo.
echo ⚠️  REQUIREMENTS:
echo    - LLVM/Clang must be installed
echo    - Download from: https://github.com/llvm/llvm-project/releases
echo    - Or install via: winget install LLVM.LLVM
echo.

set /p continue="Continue with build? (y/n): "
if /i not "%continue%"=="y" (
    echo Build cancelled
    pause
    exit /b 0
)

echo.
echo Building Agent Guru with Whisper...
cargo build --release --bin agent_guru_voice --features whisper

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Build failed
    echo.
    echo If you see "Unable to find libclang" error:
    echo 1. Install LLVM: winget install LLVM.LLVM
    echo 2. Add to PATH: C:\Program Files\LLVM\bin
    echo 3. Restart terminal and try again
    echo.
    echo Alternatively, build without Whisper:
    echo    cargo build --release --bin agent_guru_voice
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✅ Setup Complete!
echo ========================================
echo.
echo Run Agent Guru with:
echo    target\release\agent_guru_voice.exe
echo.
pause
