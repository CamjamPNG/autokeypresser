import hashlib
import json
import re
from pathlib import Path

THEME_MAGIC = b"AKPTHEME"
THEME_VERSION = 1
THEME_DIR = Path.home() / ".autokeypresser" / "themes"
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

_BASE = {
    "window": "#f4f6fa",
    "panel": "#ffffff",
    "input": "#f1f3f7",
    "text": "#191c24",
    "muted_text": "#697184",
    "accent": "#5b5ce2",
    "accent_text": "#ffffff",
    "border": "#dde1ea",
    "disabled": "#aab1bf",
    "danger": "#e5484d",
    "success": "#30a46c",
}

BUILTIN_THEMES = {
    "Classic Gray": dict(_BASE),
    "Midnight": {
        **_BASE,
        "window": "#0b0d12", "panel": "#14171e", "input": "#0f1218",
        "text": "#f5f7fb", "muted_text": "#929bad", "accent": "#64a8ff",
        "border": "#282d38", "disabled": "#4c5362", "danger": "#ff6673",
        "success": "#45d09e",
    },
    "Ocean": {
        **_BASE,
        "window": "#eef8fb", "panel": "#ffffff", "input": "#e9f4f8",
        "text": "#102a36", "muted_text": "#607b87", "accent": "#087ea4",
        "border": "#cce2ea", "disabled": "#9fb7c0", "danger": "#d84f5f",
        "success": "#168b6b",
    },
    "Forest": {
        **_BASE,
        "window": "#0d1411", "panel": "#16201b", "input": "#101813",
        "text": "#edf7f0", "muted_text": "#94a99b", "accent": "#58c987",
        "border": "#2a3b31", "disabled": "#536158", "danger": "#ff6b72",
        "success": "#58c987",
    },
    "Sunset": {
        **_BASE,
        "window": "#fff6f0", "panel": "#ffffff", "input": "#fff0e8",
        "text": "#37201a", "muted_text": "#84675e", "accent": "#e5653d",
        "border": "#efd9ce", "disabled": "#bda9a1", "danger": "#d83a52",
        "success": "#2d8f66",
    },
    "Aurora": {
        **_BASE,
        "window": "#090b13", "panel": "#121622", "input": "#0d111b",
        "text": "#f5f7ff", "muted_text": "#8e98ad", "accent": "#8b7bff",
        "border": "#272d3e", "disabled": "#4b5367", "danger": "#ff647c",
        "success": "#3dd6a0",
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
