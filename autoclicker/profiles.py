import json
from pathlib import Path

PROFILE_DIR = Path.home() / ".autokeypresser"
PROFILE_FILE = PROFILE_DIR / "profiles.json"


def load_profiles():
    try:
        with open(PROFILE_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_profiles(profiles):
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_FILE, "w", encoding="utf-8") as fh:
        json.dump(profiles, fh, indent=2)
