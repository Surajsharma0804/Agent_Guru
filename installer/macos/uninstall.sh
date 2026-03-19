#!/usr/bin/env bash
# Agent Guru - macOS Uninstaller
# Removes Agent Guru and optionally user data
#
# Usage:
#   ./uninstall.sh           # Interactive
#   ./uninstall.sh --keep-data  # Remove app, keep user data

set -euo pipefail

APP_BUNDLE="AgentGuru"
APP_PATH="/Applications/$APP_BUNDLE.app"
SUPPORT_DIR="$HOME/Library/Application Support/AgentGuru"
LOGS_DIR="$HOME/Library/Logs/AgentGuru"
PREFS_FILE="$HOME/Library/Preferences/com.agentguru.app.plist"
LAUNCH_AGENT="$HOME/Library/LaunchAgents/com.agentguru.app.plist"

KEEP_DATA=0
for arg in "$@"; do
    [ "$arg" = "--keep-data" ] && KEEP_DATA=1
done

echo "=== Agent Guru Uninstaller ==="

# Remove app bundle
if [ -d "$APP_PATH" ]; then
    echo "Removing $APP_PATH..."
    rm -rf "$APP_PATH"
    echo "Application removed"
else
    echo "Application not found at $APP_PATH"
fi

# Remove launch agent (auto-start)
if [ -f "$LAUNCH_AGENT" ]; then
    launchctl unload "$LAUNCH_AGENT" 2>/dev/null || true
    rm -f "$LAUNCH_AGENT"
    echo "Launch agent removed"
fi

# Remove preferences
rm -f "$PREFS_FILE"

# Remove logs
rm -rf "$LOGS_DIR"

# Optionally remove user data
if [ "$KEEP_DATA" = "0" ]; then
    read -p "Remove conversation history and settings? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$SUPPORT_DIR"
        echo "User data removed"
    else
        echo "User data kept at: $SUPPORT_DIR"
    fi
else
    echo "User data kept at: $SUPPORT_DIR"
fi

echo ""
echo "Agent Guru has been uninstalled."
