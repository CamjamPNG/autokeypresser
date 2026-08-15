#!/usr/bin/env bash
# Build the portable .app bundle and a .dmg installer for macOS.
# Run on macOS. Requires: python3, pyinstaller.
set -e
cd "$(dirname "$0")"

python3 -m PyInstaller --noconfirm --windowed --onedir --icon img/icon.icns --name "OPAutoClicker" main.py || {
    echo "If img/icon.icns does not exist yet, create it from img/icon.png with:";
    echo "  iconutil -c icns <iconset>"; exit 1;
}

# --- Portable .app zip -------------------------------------------------------
APP=dist/OPAutoClicker.app
ditto -c -k --keepParent "$APP" dist/OPAutoClicker-Portable-macos.zip

# --- .dmg installer (requires hdiutil) ---------------------------------------
if command -v hdiutil >/dev/null 2>&1; then
    STAGE=dist/dmg
    rm -rf "$STAGE"
    mkdir -p "$STAGE"
    cp -R "$APP" "$STAGE/"
    ln -s /Applications "$STAGE/Applications"
    hdiutil create -volname "OP Auto Clicker" -srcfolder "$STAGE" \
        -ov -format UDZO dist/OPAutoClicker-macOS.dmg
fi

echo "Built dist/OPAutoClicker.app, dist/OPAutoClicker-Portable-macos.zip, dist/OPAutoClicker-macOS.dmg"
