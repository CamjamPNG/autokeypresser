#!/usr/bin/env bash
# Build the portable executable and optional Linux installer/AppImage.
# Run on Linux. Requires: python3, pyinstaller.
set -e
cd "$(dirname "$0")"

python3 -m PyInstaller --noconfirm --onefile --windowed --icon img/icon.ico --name "AutoKeyPresser" main.py

# --- Portable tarball -------------------------------------------------------
tar -czf dist/AutoKeyPresser-Portable-linux.tar.gz -C dist AutoKeyPresser

# --- .deb installer (optional, requires dpkg-deb) ---------------------------
if command -v dpkg-deb >/dev/null 2>&1; then
    PKG=dist/deb/AutoKeyPresser
    mkdir -p "$PKG/usr/bin" "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/256x256/apps"
    cp dist/AutoKeyPresser "$PKG/usr/bin/AutoKeyPresser"
    cp img/icon.png "$PKG/usr/share/icons/hicolor/256x256/apps/opautoclicker.png"
    cat > "$PKG/usr/share/applications/opautoclicker.desktop" <<EOF
[Desktop Entry]
Name=AutoKeyPresser
Comment=Cross-platform auto key/mouse presser
Exec=/usr/bin/AutoKeyPresser
Type=Application
Categories=Utility;
Icon=opautoclicker
Terminal=false
EOF
    mkdir -p "$PKG/DEBIAN"
    cat > "$PKG/DEBIAN/control" <<EOF
Package: autokeypresser
Version: 1.0
Section: utils
Priority: optional
Architecture: amd64
Maintainer: CamjamPNG <noreply@github.com>
Description: Cross-platform auto key/mouse presser
 Automatically presses keyboard keys and mouse buttons.
EOF
    dpkg-deb --build --root-owner-group "$PKG" dist/AutoKeyPresser-Linux.deb
fi

# --- AppImage (optional, requires appimagetool) -----------------------------
if command -v appimagetool >/dev/null 2>&1; then
    APP=dist/AppDir
    mkdir -p "$APP/usr/bin"
    cp dist/AutoKeyPresser "$APP/usr/bin/"
    cp img/icon.png "$APP/opautoclicker.png"
    cat > "$APP/AutoKeyPresser.desktop" <<EOF
[Desktop Entry]
Name=AutoKeyPresser
Exec=AutoKeyPresser
Type=Application
Icon=opautoclicker
Categories=Utility;
EOF
    appimagetool "$APP" dist/AutoKeyPresser-Linux.AppImage
fi

echo "Built dist/AutoKeyPresser and dist/AutoKeyPresser-Portable-linux.tar.gz"
