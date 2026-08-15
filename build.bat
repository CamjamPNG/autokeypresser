@echo off
REM Build a standalone Windows executable with PyInstaller.
pyinstaller --noconfirm --onefile --windowed --name "OPAutoClicker" main.py
