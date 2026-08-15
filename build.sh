#!/usr/bin/env bash
# Build a standalone executable with PyInstaller (Linux / macOS).
set -e
python3 -m PyInstaller --noconfirm --onefile --windowed --name "OPAutoClicker" main.py
