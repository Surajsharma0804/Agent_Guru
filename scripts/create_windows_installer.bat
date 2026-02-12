@echo off
REM AGENT_GURU Windows Installer Creator
REM Creates a Windows installer with post-installation setup

echo ╔════════════════════════════════════════════════════════════╗
echo ║     AGENT_GURU Windows Installer Creator                  ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Check if release binary exists
if not exist "target\release\agent_guru_voice.exe" (
    echo ❌ Release binary not found!
    echo    Run: cargo build --release --bin agent_guru_voice
    exit /b 1
)

echo ✅ Release binary found
echo.

REM Create installer directory structure
echo 📁 Creating installer directory structure...
mkdir installers\windows 2>nul
mkdir installers\windows\bin 2>nul
mkdir installers\windows\config 2>nul
mkdir installers\windows\scripts 2>nul

REM Copy binary
echo 📋 Copying binary...
copy target\release\agent_guru_voice.exe installers\windows\bin\

REM Copy configuration
echo 📋 Copying configuration files...
copy .kiro\llm_config.yaml installers\windows\config\ 2>nul

REM Create post-installation setup script
echo 📝 Creating post-installation setup script...
(
echo @echo off
echo echo ╔════════════════════════════════════════════════════════════╗
echo echo ║     AGENT_GURU Post-Installation Setup                    ║
echo echo ╚════════════════════════════════════════════════════════════╝
echo echo.
echo echo Welcome to AGENT_GURU! Let's get you set up.
echo echo.
echo echo AGENT_GURU can work in two modes:
echo echo   1. LOCAL MODE  - Uses Ollama ^(private, offline^)
echo echo   2. CLOUD MODE  - Uses OpenAI or Gemini APIs
echo echo.
echo choice /C 12 /M "Choose your mode"
echo.
echo if errorlevel 2 goto cloud_mode
echo if errorlevel 1 goto local_mode
echo.
echo :local_mode
echo echo.
echo echo ═══════════════════════════════════════════════════════════
echo echo LOCAL MODE SETUP
echo echo ═══════════════════════════════════════════════════════════
echo echo.
echo echo Step 1: Install Ollama
echo echo.
echo where ollama ^>nul 2^>nul
echo if %%ERRORLEVEL%% NEQ 0 ^(
echo     echo Ollama is not installed. Opening download page...
echo     start https://ollama.ai/download
echo     echo.
echo     echo Please:
echo     echo   1. Download and install Ollama from the browser
echo     echo   2. Run this setup script again after installation
echo     pause
echo     exit /b 1
echo ^)
echo.
echo echo ✅ Ollama is installed
echo echo.
echo echo Step 2: Download AI Models
echo echo.
echo echo Downloading models ^(this may take a few minutes^)...
echo ollama pull mistral:7b-instruct
echo ollama pull qwen2.5:14b-instruct
echo.
echo echo ✅ Models downloaded successfully
echo echo.
echo echo Step 3: Start Ollama Service
echo echo.
echo start /B ollama serve
echo timeout /t 3 /nobreak ^>nul
echo.
echo echo ✅ Ollama service started
echo goto setup_complete
echo.
echo :cloud_mode
echo echo.
echo echo ═══════════════════════════════════════════════════════════
echo echo CLOUD MODE SETUP
echo echo ═══════════════════════════════════════════════════════════
echo echo.
echo echo You'll need API keys from OpenAI or Google Gemini.
echo echo.
echo echo Choose your provider:
echo echo   1. OpenAI ^(ChatGPT^)
echo echo   2. Google Gemini
echo echo   3. Both
echo echo.
echo choice /C 123 /M "Select provider"
echo.
echo if errorlevel 3 goto both_providers
echo if errorlevel 2 goto gemini_provider
echo if errorlevel 1 goto openai_provider
echo.
echo :openai_provider
echo echo.
echo echo OpenAI Setup:
echo echo   1. Go to: https://platform.openai.com/api-keys
echo echo   2. Create a new API key
echo echo   3. Copy the key
echo echo.
echo set /p OPENAI_KEY="Paste your OpenAI API key: "
echo setx OPENAI_API_KEY "%%OPENAI_KEY%%"
echo echo ✅ OpenAI API key saved
echo goto setup_complete
echo.
echo :gemini_provider
echo echo.
echo echo Google Gemini Setup:
echo echo   1. Go to: https://makersuite.google.com/app/apikey
echo echo   2. Create a new API key
echo echo   3. Copy the key
echo echo.
echo set /p GEMINI_KEY="Paste your Gemini API key: "
echo setx GEMINI_API_KEY "%%GEMINI_KEY%%"
echo echo ✅ Gemini API key saved
echo goto setup_complete
echo.
echo :both_providers
echo echo.
echo echo OpenAI Setup:
echo set /p OPENAI_KEY="Paste your OpenAI API key: "
echo setx OPENAI_API_KEY "%%OPENAI_KEY%%"
echo echo.
echo echo Gemini Setup:
echo set /p GEMINI_KEY="Paste your Gemini API key: "
echo setx GEMINI_API_KEY "%%GEMINI_KEY%%"
echo echo ✅ Both API keys saved
echo.
echo :setup_complete
echo echo.
echo echo ╔════════════════════════════════════════════════════════════╗
echo echo ║     Setup Complete!                                        ║
echo echo ╚════════════════════════════════════════════════════════════╝
echo echo.
echo echo AGENT_GURU is ready to use!
echo echo.
echo echo To start AGENT_GURU:
echo echo   1. Open Command Prompt or PowerShell
echo echo   2. Run: agent_guru_voice
echo echo   3. Say "Hey Guru" or "Hey Maya" to start talking!
echo echo.
echo echo For help: agent_guru_voice --help
echo echo.
echo pause
) > installers\windows\scripts\setup.bat

REM Create README
echo 📝 Creating README...
(
echo AGENT_GURU - Voice-Driven AI Companion
echo ========================================
echo.
echo Installation Instructions:
echo.
echo 1. Run setup.bat to configure AGENT_GURU
echo 2. Follow the on-screen instructions
echo 3. Start AGENT_GURU by running: bin\agent_guru_voice.exe
echo.
echo Voice Commands:
echo - Say "Hey Guru" or "Hey Maya" to wake up
echo - Speak naturally to interact
echo - Say "Stop listening" to pause
echo - Say "Exit" or "Goodbye" to quit
echo.
echo Configuration:
echo - Config file: config\llm_config.yaml
echo - Logs: %%USERPROFILE%%\.kiro\logs\
echo.
echo Support:
echo - Documentation: https://github.com/Surajsharma0804/Agent_Guru
echo - Issues: https://github.com/Surajsharma0804/Agent_Guru/issues
echo.
) > installers\windows\README.txt

REM Create launcher script
echo 📝 Creating launcher...
(
echo @echo off
echo cd /d "%%~dp0"
echo bin\agent_guru_voice.exe
echo pause
) > installers\windows\AGENT_GURU.bat

echo.
echo ✅ Windows installer package created!
echo 📦 Location: installers\windows\
echo.
echo To distribute:
echo   1. Zip the installers\windows\ folder
echo   2. Name it: AGENT_GURU-Windows-Installer.zip
echo   3. Users extract and run setup.bat
echo.
pause
