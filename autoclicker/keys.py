import sys

MODIFIERS = ["Ctrl", "Shift", "Alt", "Win/Cmd"]


def os_modifier(display_name):
    if sys.platform == "darwin" and display_name == "Win/Cmd":
        return "command"
    return display_name.lower().split("/")[0].strip()


def _build_map():
    mapping = []
    for c in "abcdefghijklmnopqrstuvwxyz":
        mapping.append((c.upper(), c))
    for d in "0123456789":
        mapping.append((d, d))
    for i in range(1, 13):
        mapping.append((f"F{i}", f"f{i}"))
    mapping.extend(
        [
            ("Space", "space"),
            ("Enter", "enter"),
            ("Tab", "tab"),
            ("Esc", "esc"),
            ("Backspace", "backspace"),
            ("Delete", "delete"),
            ("Insert", "insert"),
            ("Home", "home"),
            ("End", "end"),
            ("Page Up", "pageup"),
            ("Page Down", "pagedown"),
            ("Up", "up"),
            ("Down", "down"),
            ("Left", "left"),
            ("Right", "right"),
            ("Print Screen", "printscreen"),
            ("Scroll Lock", "scrolllock"),
            ("Pause", "pause"),
            ("Num Lock", "numlock"),
            ("Caps Lock", "capslock"),
            ("Menu", "menu"),
        ]
    )
    return mapping


KEY_MAP = _build_map()
DISPLAY_KEYS = [display for display, _ in KEY_MAP]
DISPLAY_TO_KEY = dict(KEY_MAP)


def display_to_key(display_name):
    return DISPLAY_TO_KEY.get(display_name, display_name.lower())
