@echo off
REM GURU Audio Fix Script
REM Opens Volume Mixer so user can unmute Python

echo ================================================================================
echo GURU AUDIO FIX
echo ================================================================================
echo.
echo If you see GURU responding in text but don't hear speech, Python audio is muted.
echo.
echo This script will open Windows Volume Mixer.
echo.
echo TO FIX:
echo   1. Find "python.exe" or "pythonw.exe" in the mixer
echo   2. Click the speaker icon to UNMUTE it
echo   3. Set volume slider to 100%%
echo   4. Close Volume Mixer
echo   5. GURU will now speak!
echo.
echo Press any key to open Volume Mixer...
pause >nul

echo.
echo Opening Volume Mixer...
start sndvol.exe

echo.
echo Volume Mixer opened!
echo.
echo After unmuting Python:
echo   - GURU should speak immediately
echo   - If not, restart GURU
echo.
pause
