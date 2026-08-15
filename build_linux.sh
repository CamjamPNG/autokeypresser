#!/usr/bin/env bash
# Build the portable executable and optional Linux installer/AppImage.
# Run on Linux. Requires: python3, pyinstaller.
set -e
cd "$(dirname "$0")"

python3 -m PyInstaller --noconfirm --onefile --windowed --icon img/icon.ico --name "OPAutoClicker" main.py

# --- Portable tarball -------------------------------------------------------
tar -czf dist/OPAutoClicker-Portable-linux.tar.gz -C dist OPAutoClicker

# --- .deb installer (optional, requires dpkg-deb) ---------------------------
if command -v dpkg-deb >/dev/null 2>&1; then
    PKG=dist/deb/OPAutoClicker
    mkdir -p "$PKG/usr/bin" "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/256x256/apps"
    cp dist/OPAutoClicker "$PKG/usr/bin/OPAutoClicker"
    cp img/icon.png "$PKG/usr/share/icons/hicolor/256x256/apps/opautoclicker.png"
    cat > "$PKG/usr/share/applications/opautoclicker.desktop" <<EOF
[Desktop Entry]
Name=OP Auto Clicker
Comment=Cross-platform auto key/mouse presser
Exec=/usr/bin/OPAutoClicker
Type=Application
Categories=Utility;
Icon=opautoclicker
Terminal=false
EOF
    mkdir -p "$PKG/DEBIAN"
    cat > "$PKG/DEBIAN/control" <<EOF
Package: op-auto-clicker
Version: 2.1
Section: utils
Priority: optional
Architecture: amd64
Maintainer: CamjamPNG <noreply@github.com>
Description: Cross-platform auto key/mouse presser
 Automatically presses keyboard keys and mouse buttons.
EOF
    dpkg-deb --build --root-owner-group "$PKG" dist/OPAutoClicker-Linux.deb
fi

# --- AppImage (optional, requires appimagetool) -----------------------------
if command -v appimagetool >/dev/null 2>&1; then
    APP=dist/AppDir
    mkdir -p "$APP/usr/bin"
    cp dist/OPAutoClicker "$APP/usr/bin/"
    cp img/icon.png "$APP/opautoclicker.png"
    cat > "$APP/OPAutoClicker.desktop" <<EOF
[Desktop Entry]
Name=OP Auto Clicker
Exec=OPAutoClicker
Type=Application
Icon=opautoclicker
Categories=Utility;
EOF
    appimagetool "$APP" dist/OPAutoClicker-Linux.AppImage
fi

echo "Built dist/OPAutoClicker and dist/OPAutoClicker-Portable-linux.tar.gz"
