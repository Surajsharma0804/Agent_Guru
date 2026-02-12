@echo off
echo ╔════════════════════════════════════════════════════════════╗
echo ║     Agent Guru Post-Installation Setup                    ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo Welcome to Agent Guru! Let's get you set up.
echo.
echo Agent Guru can work in two modes:
echo   1. LOCAL MODE  - Uses Ollama (private, offline)
echo   2. CLOUD MODE  - Uses OpenAI or Gemini APIs
echo.
choice /C 12 /M "Choose your mode"

if errorlevel 2 goto cloud_mode
if errorlevel 1 goto local_mode

:local_mode
echo.
echo ═══════════════════════════════════════════════════════════
echo LOCAL MODE SETUP
echo ═══════════════════════════════════════════════════════════
echo.
echo Step 1: Install Ollama
echo.
where ollama >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Ollama is not installed. Opening download page...
    start https://ollama.ai/download
    echo.
    echo Please:
    echo   1. Download and install Ollama from the browser
    echo   2. Run this setup script again after installation
    pause
    exit /b 1
)

echo ✅ Ollama is installed
echo.
echo Step 2: Download AI Models
echo.
echo Downloading models (this may take a few minutes)...
ollama pull mistral:7b-instruct
ollama pull qwen2.5:14b-instruct

echo ✅ Models downloaded successfully
echo.
echo Step 3: Start Ollama Service
echo.
start /B ollama serve
timeout /t 3 /nobreak >nul

echo ✅ Ollama service started
goto setup_complete

:cloud_mode
echo.
echo ═══════════════════════════════════════════════════════════
echo CLOUD MODE SETUP
echo ═══════════════════════════════════════════════════════════
echo.
echo You'll need API keys from OpenAI or Google Gemini.
echo.
echo Choose your provider:
echo   1. OpenAI (ChatGPT)
echo   2. Google Gemini
echo   3. Both
echo.
choice /C 123 /M "Select provider"

if errorlevel 3 goto both_providers
if errorlevel 2 goto gemini_provider
if errorlevel 1 goto openai_provider

:openai_provider
echo.
echo OpenAI Setup:
echo   1. Go to: https://platform.openai.com/api-keys
echo   2. Create a new API key
echo   3. Copy the key
echo.
set /p OPENAI_KEY="Paste your OpenAI API key: "
setx OPENAI_API_KEY "%OPENAI_KEY%"
echo ✅ OpenAI API key saved
goto setup_complete

:gemini_provider
echo.
echo Google Gemini Setup:
echo   1. Go to: https://makersuite.google.com/app/apikey
echo   2. Create a new API key
echo   3. Copy the key
echo.
set /p GEMINI_KEY="Paste your Gemini API key: "
setx GEMINI_API_KEY "%GEMINI_KEY%"
echo ✅ Gemini API key saved
goto setup_complete

:both_providers
echo.
echo OpenAI Setup:
set /p OPENAI_KEY="Paste your OpenAI API key: "
setx OPENAI_API_KEY "%OPENAI_KEY%"
echo.
echo Gemini Setup:
set /p GEMINI_KEY="Paste your Gemini API key: "
setx GEMINI_API_KEY "%GEMINI_KEY%"
echo ✅ Both API keys saved

:setup_complete
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║     Setup Complete!                                        ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
echo Agent Guru is ready to use!
echo.
echo To start Agent Guru:
echo   1. Open Command Prompt or PowerShell
echo   2. Run: agent_guru_voice
echo   3. Say "Hey Guru" or "Hey Maya" to start talking!
echo.
echo For help: agent_guru_voice --help
echo.
pause
