@echo off
REM Create LLM configuration with correct Ollama model

echo ========================================
echo Creating LLM Configuration
echo ========================================
echo.

REM Create .guru directory in user home
if not exist "%USERPROFILE%\.guru" (
    echo Creating .guru directory...
    mkdir "%USERPROFILE%\.guru"
)

REM Create llm_config.json with correct model
echo Creating llm_config.json...
(
echo {
echo   "mode": "local",
echo   "default_provider": "ollama",
echo   "enable_fallback": true,
echo   "enable_audit_logging": true,
echo   "fail_closed_on_error": true,
echo   "providers": {
echo     "ollama": {
echo       "enabled": true,
echo       "base_url": "http://localhost:11434",
echo       "models": [
echo         "qwen2.5:7b-instruct",
echo         "qwen2.5:14b-instruct",
echo         "mistral:7b-instruct"
echo       ],
echo       "default_model": "qwen2.5:7b-instruct",
echo       "require_manual_confirmation": false,
echo       "require_armed_authority": false,
echo       "timeout_seconds": 30,
echo       "max_concurrent_requests": 5
echo     },
echo     "openai": {
echo       "enabled": false,
echo       "api_key": null,
echo       "models": ["gpt-3.5-turbo", "gpt-4"],
echo       "default_model": "gpt-3.5-turbo",
echo       "require_manual_confirmation": true,
echo       "require_armed_authority": true,
echo       "timeout_seconds": 30,
echo       "max_concurrent_requests": 3
echo     },
echo     "gemini": {
echo       "enabled": false,
echo       "api_key": null,
echo       "models": ["gemini-pro", "gemini-1.5-pro"],
echo       "default_model": "gemini-pro",
echo       "require_manual_confirmation": true,
echo       "require_armed_authority": true,
echo       "timeout_seconds": 30,
echo       "max_concurrent_requests": 3
echo     }
echo   },
echo   "tasks": {
echo     "intent_extraction": {
echo       "provider": "ollama",
echo       "model": "qwen2.5:7b-instruct",
echo       "enabled": true,
echo       "fallback_provider": null,
echo       "fallback_model": null,
echo       "timeout_seconds": 30,
echo       "max_retries": 2
echo     },
echo     "intent_structuring": {
echo       "provider": "ollama",
echo       "model": "mistral:7b-instruct",
echo       "enabled": true,
echo       "fallback_provider": null,
echo       "fallback_model": null,
echo       "timeout_seconds": 30,
echo       "max_retries": 2
echo     },
echo     "conversation": {
echo       "provider": "ollama",
echo       "model": "qwen2.5:7b-instruct",
echo       "enabled": true,
echo       "fallback_provider": null,
echo       "fallback_model": null,
echo       "timeout_seconds": 30,
echo       "max_retries": 2
echo     },
echo     "deep_reasoning": {
echo       "provider": "ollama",
echo       "model": "qwen2.5:14b-instruct",
echo       "enabled": true,
echo       "fallback_provider": null,
echo       "fallback_model": null,
echo       "timeout_seconds": 60,
echo       "max_retries": 1
echo     }
echo   }
echo }
) > "%USERPROFILE%\.guru\llm_config.json"

echo.
echo ========================================
echo Configuration Created Successfully!
echo ========================================
echo.
echo Location: %USERPROFILE%\.guru\llm_config.json
echo.
echo Models configured:
echo   - Conversation: qwen2.5:7b-instruct
echo   - Intent Extraction: qwen2.5:7b-instruct
echo   - Intent Structuring: mistral:7b-instruct
echo   - Deep Reasoning: qwen2.5:14b-instruct
echo.
echo All models match your installed Ollama models!
echo.
pause
