import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".op_auto_clicker"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "input_type": "mouse",
    "mouse_button": "left",
    "key": "a",
    "modifiers": [],
    "click_type": "single",
    "repeat_until_stopped": True,
    "repeat_count": 1,
    "hours": "0",
    "mins": "0",
    "secs": "0",
    "ms": "100",
    "use_fixed_position": False,
    "x": "0",
    "y": "0",
    "hotkey_mod": "None",
    "hotkey_key": "F6",
}


def load_config():
    data = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, encoding="utf-8") as fh:
            saved = json.load(fh)
        data.update({key: saved[key] for key in data if key in saved})
    except (OSError, ValueError):
        pass
    return data


def save_config(config):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(config, fh, indent=2)
    except OSError:
        pass
