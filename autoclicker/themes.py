import hashlib
import json
import re
from pathlib import Path

THEME_MAGIC = b"AKPTHEME"
THEME_VERSION = 1
THEME_DIR = Path.home() / ".autokeypresser" / "themes"
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

_BASE = {
    "window": "#f0f0f0",
    "panel": "#f0f0f0",
    "input": "#ffffff",
    "text": "#000000",
    "muted_text": "#555555",
    "accent": "#0078d4",
    "accent_text": "#ffffff",
    "border": "#808080",
    "disabled": "#d0d0d0",
    "danger": "#c62828",
}

BUILTIN_THEMES = {
    "Classic Gray": dict(_BASE),
    "Midnight": {
        **_BASE,
        "window": "#202124", "panel": "#292a2d", "input": "#17181a",
        "text": "#f5f7fa", "muted_text": "#b8bcc4", "accent": "#4ea1ff",
        "border": "#555a64", "disabled": "#3a3d42", "danger": "#ff6b6b",
    },
    "Ocean": {
        **_BASE,
        "window": "#e8f4fb", "panel": "#d8edf7", "input": "#ffffff",
        "text": "#123044", "muted_text": "#466879", "accent": "#087eaa",
        "border": "#78afc4", "disabled": "#c6dce5",
    },
    "Forest": {
        **_BASE,
        "window": "#eaf3eb", "panel": "#d9e9da", "input": "#ffffff",
        "text": "#173b22", "muted_text": "#52705a", "accent": "#2f7d4a",
        "border": "#86a88c", "disabled": "#c8d9ca",
    },
    "Sunset": {
        **_BASE,
        "window": "#fff1e6", "panel": "#ffe2cc", "input": "#fffaf5",
        "text": "#432415", "muted_text": "#805b49", "accent": "#c95d2e",
        "border": "#c89a7c", "disabled": "#ead2c2", "danger": "#a52a2a",
    },
}


class ThemeFormatError(ValueError):
    pass


def theme_names():
    return list(BUILTIN_THEMES)


def validate_theme(theme):
    if not isinstance(theme, dict) or not isinstance(theme.get("colors"), dict):
        raise ThemeFormatError("A theme must contain a colors object.")
    colors = {**_BASE, **theme["colors"]}
    for key in _BASE:
        if not _HEX.match(str(colors.get(key, ""))):
            raise ThemeFormatError("Invalid color for theme property: %s" % key)
    font = theme.get("font", {})
    if not isinstance(font, dict) or not 6 <= int(font.get("size", 9)) <= 32:
        raise ThemeFormatError("Theme font size must be between 6 and 32.")
    return {**theme, "colors": colors, "font": {"family": str(font.get("family", "TkDefaultFont")), "size": int(font.get("size", 9))}}


def make_theme(name):
    return validate_theme({
        "format": "AutoKeyPresser Theme",
        "version": THEME_VERSION,
        "name": name,
        "author": "AutoKeyPresser",
        "colors": BUILTIN_THEMES[name],
        "font": {"family": "TkDefaultFont", "size": 9},
    })


def save_theme(theme, path):
    theme = validate_theme(theme)
    data = json.dumps(theme, indent=2, sort_keys=True).encode("utf-8")
    content = THEME_MAGIC + bytes([THEME_VERSION]) + data
    checksum = hashlib.sha256(content).hexdigest().encode("ascii")
    with open(path, "wb") as handle:
        handle.write(content + b"\n" + checksum)


def load_theme(path):
    with open(path, "rb") as handle:
        raw = handle.read()
    if len(raw) < len(THEME_MAGIC) + 1 + 1 + 64:
        raise ThemeFormatError("The file is too small to be an AutoKeyPresser theme.")
    content, checksum = raw[:-65], raw[-64:]
    if hashlib.sha256(content).hexdigest().encode("ascii") != checksum:
        raise ThemeFormatError("Theme checksum mismatch; the file may be corrupt or modified.")
    if not content.startswith(THEME_MAGIC) or content[len(THEME_MAGIC)] != THEME_VERSION:
        raise ThemeFormatError("Unsupported AutoKeyPresser theme format.")
    try:
        theme = json.loads(content[len(THEME_MAGIC) + 1:].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ThemeFormatError("The theme payload is invalid.") from exc
    if theme.get("format") != "AutoKeyPresser Theme":
        raise ThemeFormatError("This is not an AutoKeyPresser theme.")
    return validate_theme(theme)


def save_user_theme(theme):
    THEME_DIR.mkdir(parents=True, exist_ok=True)
    path = THEME_DIR / (theme["name"].strip().replace(" ", "_") + ".akpt")
    save_theme(theme, path)
    return path


def load_user_theme(name):
    path = THEME_DIR / (name.strip().replace(" ", "_") + ".akpt")
    return load_theme(path)
