#!/usr/bin/env bash
# Agent Guru - build the small macOS installer, a .dmg, into dist/.
#
# Run this on a Mac, on the chip you want to build for: PyInstaller cannot
# cross-compile, so an Apple Silicon Mac builds an arm64 app and an Intel Mac
# an x86_64 one. It freezes only the launcher and carries the application
# source. Packages and models are installed by GENESIS after the person
# approves a plan, into ~/Library/Application Support/AgentGuru.
#
# Needs: Python 3.11 to 3.13 (python3), and the Xcode Command Line Tools
# (xcode-select --install). hdiutil comes with macOS. From the repository root:
#   ./installer/macos/build_dmg.sh
#
# The app is not signed or notarized, so Gatekeeper blocks a double-click. The
# first time: right-click the app, choose Open, then Open again. Removing that
# step needs a paid Apple Developer ID.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="${WORK:-$HOME/Library/Caches/agent-guru-build}"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$ROOT/pyproject.toml" | head -1)"
ARCH="$(uname -m)"
OUT="$ROOT/dist/AgentGuru-$VERSION-$ARCH.dmg"

started=$SECONDS
mkdir -p "$WORK" "$ROOT/dist"
if [ ! -x "$WORK/venv/bin/python" ]; then
    python3 -m venv "$WORK/venv"
fi
"$WORK/venv/bin/python" -m pip install --quiet --disable-pip-version-check pyinstaller pyinstaller-hooks-contrib pywebview \
    -c "$ROOT/requirements-lock.txt"

cd "$ROOT"
"$WORK/venv/bin/python" -m PyInstaller AgentGuru.spec --noconfirm --distpath "$WORK/dist" --workpath "$WORK/build"

STAGE="$WORK/stage"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$WORK/dist/Agent Guru.app" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$OUT"
hdiutil create -volname "Agent Guru" -srcfolder "$STAGE" -ov -format UDZO "$OUT"
echo "$OUT: $(( $(stat -f %z "$OUT") / 1000000 )) MB in $(( SECONDS - started )) s"
