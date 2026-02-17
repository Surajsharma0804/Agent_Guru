@echo off
REM Development environment setup script for Core Reasoning Engine (Windows)

echo 🚀 Setting up Core Reasoning Engine development environment...

REM Check Python version
echo 📋 Checking Python version...
python --version
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Python is not installed or not in PATH
    exit /b 1
)

REM Create virtual environment
echo 📦 Creating virtual environment...
if not exist "venv" (
    python -m venv venv
    echo ✅ Virtual environment created
) else (
    echo ℹ️  Virtual environment already exists
)

REM Activate virtual environment
echo 🔌 Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo ⬆️  Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo 📥 Installing dependencies...
pip install -e ".[dev]"

REM Install pre-commit hooks
echo 🪝 Installing pre-commit hooks...
pre-commit install

REM Run initial checks
echo 🔍 Running initial code quality checks...
black --check Agent_Guru\reasoning
ruff check Agent_Guru\reasoning
mypy Agent_Guru\reasoning

echo.
echo ✅ Development environment setup complete!
echo.
echo Next steps:
echo   1. Activate the virtual environment: venv\Scripts\activate.bat
echo   2. Run tests: pytest
echo   3. Start development!
echo.
echo Useful commands:
echo   - Format code: black .
echo   - Lint code: ruff check .
echo   - Type check: mypy .
echo   - Run tests: pytest
echo   - Run with coverage: pytest --cov
