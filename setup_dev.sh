#!/bin/bash
# Development environment setup script for Core Reasoning Engine

set -e

echo "🚀 Setting up Core Reasoning Engine development environment..."

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required_version="3.11"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.11+ is required. Found: $python_version"
    exit 1
fi
echo "✅ Python version: $python_version"

# Create virtual environment
echo "📦 Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "ℹ️  Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies..."
pip install -e ".[dev]"

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
pre-commit install

# Run initial checks
echo "🔍 Running initial code quality checks..."
black --check Agent_Guru/reasoning/ || true
ruff check Agent_Guru/reasoning/ || true
mypy Agent_Guru/reasoning/ || true

echo ""
echo "✅ Development environment setup complete!"
echo ""
echo "Next steps:"
echo "  1. Activate the virtual environment: source venv/bin/activate"
echo "  2. Run tests: pytest"
echo "  3. Start development!"
echo ""
echo "Useful commands:"
echo "  - Format code: black ."
echo "  - Lint code: ruff check ."
echo "  - Type check: mypy ."
echo "  - Run tests: pytest"
echo "  - Run with coverage: pytest --cov"
