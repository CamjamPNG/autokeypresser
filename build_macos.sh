#!/usr/bin/env bash
# Build the portable .app bundle and a .dmg installer for macOS.
# Run on macOS. Requires: python3, pyinstaller.
set -e
cd "$(dirname "$0")"

ICON_ARGS=()
if command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
    ICONSET=dist/AutoKeyPresser.iconset
    rm -rf "$ICONSET" dist/AutoKeyPresser.icns
    mkdir -p "$ICONSET"
    for size in 16 32 128 256 512; do
        sips -z "$size" "$size" img/icon.png --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
        double=$((size * 2))
        sips -z "$double" "$double" img/icon.png --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
    done
    iconutil -c icns "$ICONSET" -o dist/AutoKeyPresser.icns
    ICON_ARGS=(--icon dist/AutoKeyPresser.icns)
fi

python3 -m PyInstaller --noconfirm --windowed --onedir "${ICON_ARGS[@]}" --name "AutoKeyPresser" main.py

# --- Portable .app zip -------------------------------------------------------
APP=dist/AutoKeyPresser.app
ditto -c -k --keepParent "$APP" dist/AutoKeyPresser-Portable-macos.zip

# --- .dmg installer (requires hdiutil) ---------------------------------------
if command -v hdiutil >/dev/null 2>&1; then
    STAGE=dist/dmg
    rm -rf "$STAGE"
    mkdir -p "$STAGE"
    cp -R "$APP" "$STAGE/"
    ln -s /Applications "$STAGE/Applications"
    hdiutil create -volname "AutoKeyPresser" -srcfolder "$STAGE" \
        -ov -format UDZO dist/AutoKeyPresser-macOS.dmg
fi

echo "Built dist/AutoKeyPresser.app, dist/AutoKeyPresser-Portable-macos.zip, dist/AutoKeyPresser-macOS.dmg"
