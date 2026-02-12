#!/bin/bash
# AGENT_GURU Installer Build Script
# Builds Windows .exe and macOS .app installers

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     AGENT_GURU Installer Builder                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Detect platform
PLATFORM=$(uname -s)
echo "Platform detected: $PLATFORM"
echo ""

# Build release binary
echo "🔨 Building release binary..."
cargo build --release --bin agent_guru_voice

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi

echo "✅ Build successful"
echo ""

# Create installers directory
mkdir -p installers

# Platform-specific installer creation
case "$PLATFORM" in
    Darwin)
        echo "🍎 Creating macOS .app bundle..."
        ./scripts/create_macos_app.sh
        ;;
    Linux)
        echo "🐧 Creating Linux installer..."
        echo "⚠️  Linux installer not yet implemented"
        echo "   Use: cargo install --path ."
        ;;
    MINGW*|MSYS*|CYGWIN*)
        echo "🪟 Creating Windows installer..."
        ./scripts/create_windows_installer.bat
        ;;
    *)
        echo "❌ Unsupported platform: $PLATFORM"
        exit 1
        ;;
esac

echo ""
echo "✅ Installer creation complete!"
echo "📦 Installers available in: ./installers/"
echo ""
