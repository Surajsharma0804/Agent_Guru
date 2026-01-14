@echo off
REM GURU Fresh Install Script
REM Complete clean installation from scratch

echo ================================================================================
echo GURU FRESH INSTALLATION
echo ================================================================================
echo.
echo This will:
echo   1. Uninstall any existing GURU installation
echo   2. Clean all configuration and data
echo   3. Start GURU with first-time setup
echo.
echo Press Ctrl+C to cancel or any key to continue...
pause >nul

echo.
echo Step 1: Running complete uninstall...
call COMPLETE_UNINSTALL.bat

echo.
echo Step 2: Verifying Python dependencies...
python -c "import PyQt6" 2>nul
if errorlevel 1 (
    echo ERROR: PyQt6 not installed
    echo Installing PyQt6...
    pip install PyQt6
)

python -c "import pyttsx3" 2>nul
if errorlevel 1 (
    echo ERROR: pyttsx3 not installed
    echo Installing pyttsx3...
    pip install pyttsx3
)

python -c "import speech_recognition" 2>nul
if errorlevel 1 (
    echo ERROR: SpeechRecognition not installed
    echo Installing SpeechRecognition...
    pip install SpeechRecognition
)

echo.
echo Step 3: Running diagnostic...
python DIAGNOSE_SPEECH.py

echo.
echo Step 4: Starting GURU...
echo.
echo ================================================================================
echo GURU WILL NOW START
echo ================================================================================
echo.
echo You will see the setup wizard.
echo Follow the instructions in FRESH_START_INSTRUCTIONS.md
echo.
pause

python launch_guru_complete.py

pause
