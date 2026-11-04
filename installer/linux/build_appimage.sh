#!/usr/bin/env bash
# Agent Guru - build the small Linux installer, an AppImage, into dist/.
#
# One file that runs on most x86-64 distributions with no root. It carries the
# frozen launcher and the application source; packages and models are installed
# by GENESIS after the person approves a plan, into ~/.local/share/AgentGuru.
#
# Needs: python3, squashfs-tools (mksquashfs), curl. Run from anywhere, on
# Linux or in WSL:
#   installer/linux/build_appimage.sh
#
# Build files stay outside the repository (WORK), because a Windows drive under
# WSL is slow and keeps no Unix file modes. Only the AppImage lands in dist/.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="${WORK:-$HOME/.cache/agent-guru-build}"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$ROOT/pyproject.toml" | head -1)"
OUT="$ROOT/dist/AgentGuru-$VERSION-x86_64.AppImage"

# The AppImage stub. Upstream publishes it only under a moving "continuous" tag,
# so the hash is the pin: a changed stub stops the build instead of shipping.
RUNTIME_URL="https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64"
RUNTIME_SHA256="617aa77314d57c8b8e4fae9c3f0b35af7b30d5529cb69e98f64f92510ed98a46"

started=$SECONDS
mkdir -p "$WORK" "$ROOT/dist"
if [ ! -x "$WORK/venv/bin/python" ]; then
    python3 -m venv "$WORK/venv"
fi
# No pywebview here: its GTK bindings cannot be frozen into a portable file,
# so on Linux the window is the default browser (Decision 5's fallback).
"$WORK/venv/bin/python" -m pip install --quiet --disable-pip-version-check pyinstaller pyinstaller-hooks-contrib \
    -c "$ROOT/requirements-lock.txt"

cd "$ROOT"
"$WORK/venv/bin/python" -m PyInstaller AgentGuru.spec --noconfirm --distpath "$WORK/dist" --workpath "$WORK/build"

APPDIR="$WORK/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib"
cp -a "$WORK/dist/AgentGuru" "$APPDIR/usr/lib/AgentGuru"
cp "$ROOT/assets/icon.png" "$APPDIR/agent-guru.png"
cat > "$APPDIR/agent-guru.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Agent Guru
Comment=Your intelligence. Your machine. Your rules.
Exec=AgentGuru
Icon=agent-guru
Categories=Utility;
Terminal=false
DESKTOP
cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
# "genesis ..." on the command line goes to the console build, so it can print.
here="$(dirname "$(readlink -f "$0")")"
if [ "$1" = "genesis" ]; then
    exec "$here/usr/lib/AgentGuru/AgentGuruCli" "$@"
fi
exec "$here/usr/lib/AgentGuru/AgentGuru" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

if [ ! -f "$WORK/runtime-x86_64" ] || ! echo "$RUNTIME_SHA256  $WORK/runtime-x86_64" | sha256sum -c --status; then
    curl -fsSL -o "$WORK/runtime-x86_64" "$RUNTIME_URL"
fi
echo "$RUNTIME_SHA256  $WORK/runtime-x86_64" | sha256sum -c --status

rm -f "$WORK/app.squashfs"
mksquashfs "$APPDIR" "$WORK/app.squashfs" -root-owned -noappend -comp zstd -Xcompression-level 19 -quiet
cat "$WORK/runtime-x86_64" "$WORK/app.squashfs" > "$WORK/out.AppImage"
chmod +x "$WORK/out.AppImage"
cp "$WORK/out.AppImage" "$OUT"
chmod +x "$OUT" 2>/dev/null || true
echo "$OUT: $(( $(stat -c %s "$OUT") / 1000000 )) MB in $(( SECONDS - started )) s"
