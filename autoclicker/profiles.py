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


def move_step(actions, index, offset):
    """Return a copy of actions with one step shifted by offset.

    An index outside the list, or a move that would leave it, returns the order
    unchanged instead of wrapping a step to the other end.
    """
    steps = list(actions)
    if not 0 <= index < len(steps):
        return steps
    target = index + offset
    if not 0 <= target < len(steps):
        return steps
    steps.insert(target, steps.pop(index))
    return steps


def remove_step(actions, index):
    """Return a copy of actions without the step at index."""
    steps = list(actions)
    if not 0 <= index < len(steps):
        return steps
    del steps[index]
    return steps


def replace_step(actions, index, action):
    """Return a copy of actions with the step at index swapped for action."""
    steps = list(actions)
    if not 0 <= index < len(steps):
        return steps
    steps[index] = action
    return steps


def with_steps(profiles, name, actions):
    """Return a copy of profiles where name holds exactly actions as its steps.

    Only the "actions" key is replaced, so a profile keeps any other fields it
    already stores and the profile JSON shape stays what it was.
    """
    updated = dict(profiles)
    profile = dict(updated.get(name) or {})
    profile["actions"] = list(actions)
    updated[name] = profile
    return updated
