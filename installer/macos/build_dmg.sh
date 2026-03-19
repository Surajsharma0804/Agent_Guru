#!/usr/bin/env bash
# Agent Guru - macOS DMG Installer Build Script
# Builds a signed .app bundle and packages it in a DMG
#
# Prerequisites:
#   - macOS 11+ (Big Sur or later)
#   - Python 3.11+ with Agent Guru dependencies installed
#   - PyInstaller: pip install pyinstaller
#   - create-dmg: brew install create-dmg
#   - Xcode Command Line Tools: xcode-select --install
#   - Apple Developer ID (for signing/notarization)
#
# Usage:
#   ./installer/macos/build_dmg.sh
#   VERSION=1.0.1 SIGN=1 ./installer/macos/build_dmg.sh

set -euo pipefail

# -------------------------------------------------------
# Configuration
# -------------------------------------------------------
APP_NAME="Agent Guru"
APP_BUNDLE="AgentGuru"
VERSION="${VERSION:-1.0.0}"
SIGN="${SIGN:-0}"
NOTARIZE="${NOTARIZE:-0}"
DEVELOPER_ID="${DEVELOPER_ID:-Developer ID Application: Agent Guru Team}"
APPLE_ID="${APPLE_ID:-}"
TEAM_ID="${TEAM_ID:-}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="$ROOT_DIR/dist/macos"
BUILD_DIR="$ROOT_DIR/build/macos"
INSTALLER_DIR="$ROOT_DIR/installer/macos"
APP_BUNDLE_PATH="$DIST_DIR/$APP_BUNDLE.app"
DMG_PATH="$INSTALLER_DIR/${APP_BUNDLE}-${VERSION}.dmg"

echo "=== Agent Guru macOS Installer Build ==="
echo "Version: $VERSION"
echo "Root: $ROOT_DIR"
echo "Sign: $SIGN"

# -------------------------------------------------------
# Step 1: Verify requirements
# -------------------------------------------------------
echo ""
echo "[1/5] Verifying requirements..."

python3 installer/verify_requirements.py || {
    echo "ERROR: System requirements check failed."
    exit 1
}

command -v pyinstaller >/dev/null 2>&1 || {
    echo "Installing PyInstaller..."
    pip install pyinstaller --quiet
}

command -v create-dmg >/dev/null 2>&1 || {
    echo "ERROR: create-dmg not found. Install with: brew install create-dmg"
    exit 1
}

echo "Requirements OK"

# -------------------------------------------------------
# Step 2: Build .app bundle with PyInstaller
# -------------------------------------------------------
echo ""
echo "[2/5] Building .app bundle..."

mkdir -p "$DIST_DIR" "$BUILD_DIR"

pyinstaller \
    --name "$APP_BUNDLE" \
    --onedir \
    --windowed \
    --icon "assets/icon.icns" \
    --add-data "models:models" \
    --add-data "assets:assets" \
    --add-data "Agent_Guru:Agent_Guru" \
    --hidden-import "Agent_Guru.speech" \
    --hidden-import "Agent_Guru.vision" \
    --hidden-import "Agent_Guru.llm" \
    --hidden-import "Agent_Guru.platform" \
    --hidden-import "Agent_Guru.agents" \
    --hidden-import "Agent_Guru.memory" \
    --hidden-import "Agent_Guru.security" \
    --hidden-import "Agent_Guru.policy" \
    --hidden-import "Agent_Guru.avatar" \
    --osx-bundle-identifier "com.agentguru.app" \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR" \
    --noconfirm \
    "Agent_Guru/__main__.py"

echo ".app bundle built"

# -------------------------------------------------------
# Step 3: Update Info.plist
# -------------------------------------------------------
echo ""
echo "[3/5] Updating Info.plist..."

PLIST="$APP_BUNDLE_PATH/Contents/Info.plist"

/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :NSMicrophoneUsageDescription 'Agent Guru needs microphone access for voice commands'" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :NSCameraUsageDescription 'Agent Guru needs camera access for face recognition'" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string '11.0'" "$PLIST" 2>/dev/null || \
/usr/libexec/PlistBuddy -c "Set :LSMinimumSystemVersion '11.0'" "$PLIST"

echo "Info.plist updated"

# -------------------------------------------------------
# Step 4: Code signing (optional)
# -------------------------------------------------------
if [ "$SIGN" = "1" ]; then
    echo ""
    echo "[4/5] Signing application..."

    codesign \
        --force \
        --deep \
        --sign "$DEVELOPER_ID" \
        --options runtime \
        --entitlements "$INSTALLER_DIR/entitlements.plist" \
        "$APP_BUNDLE_PATH"

    codesign --verify --deep --strict "$APP_BUNDLE_PATH"
    echo "Signing complete"

    # Notarization
    if [ "$NOTARIZE" = "1" ] && [ -n "$APPLE_ID" ] && [ -n "$TEAM_ID" ]; then
        echo "Notarizing..."
        xcrun notarytool submit "$APP_BUNDLE_PATH" \
            --apple-id "$APPLE_ID" \
            --team-id "$TEAM_ID" \
            --wait
        xcrun stapler staple "$APP_BUNDLE_PATH"
        echo "Notarization complete"
    fi
else
    echo ""
    echo "[4/5] Skipping code signing (SIGN=0)"
fi

# -------------------------------------------------------
# Step 5: Create DMG
# -------------------------------------------------------
echo ""
echo "[5/5] Creating DMG..."

rm -f "$DMG_PATH"

create-dmg \
    --volname "$APP_NAME $VERSION" \
    --volicon "assets/icon.icns" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "$APP_BUNDLE.app" 175 190 \
    --hide-extension "$APP_BUNDLE.app" \
    --app-drop-link 425 190 \
    --background "$INSTALLER_DIR/dmg_background.png" \
    "$DMG_PATH" \
    "$DIST_DIR/"

echo ""
echo "=== Build Complete ==="
echo "DMG: $DMG_PATH"
echo "Size: $(du -sh "$DMG_PATH" | cut -f1)"
