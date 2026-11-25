import copy
import json
from pathlib import Path

PROFILE_DIR = Path.home() / ".autokeypresser"
PROFILE_FILE = PROFILE_DIR / "profiles.json"

DELAY_FIELD = "delay_ms"


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


def step_delay_seconds(action):
    """Return the step's own delay in seconds, or None for the global interval.

    An action without the field, or with a value this build cannot read, falls
    back to the global interval instead of failing, so a file written by hand or
    by a newer build still runs.
    """
    raw = (
        action.get(DELAY_FIELD)
        if isinstance(action, dict)
        else getattr(action, DELAY_FIELD, None)
    )
    if raw is None or raw == "":
        return None
    try:
        milliseconds = float(raw)
    except (TypeError, ValueError):
        return None
    if not milliseconds >= 0:
        return None
    return milliseconds / 1000.0


def with_step_delay(actions, index, milliseconds):
    """Return a copy of actions with one step's own delay set, or cleared when None.

    The copy keeps the working list apart from the stored snapshot, so staging a
    delay never changes what unsaved_changes() compares against.
    """
    steps = copy.deepcopy(list(actions))
    if not 0 <= index < len(steps):
        return steps
    if milliseconds is None:
        steps[index].pop(DELAY_FIELD, None)
    else:
        steps[index][DELAY_FIELD] = int(milliseconds)
    return steps


def sequence_actions(actions):
    """The queued steps a run needs, or an empty list for one plain step.

    A single step that carries its own delay stays in the queue, because the
    delay lives on the step and the action card has no field of its own.
    """
    steps = list(actions)
    if len(steps) > 1 or (steps and step_delay_seconds(steps[0]) is not None):
        return copy.deepcopy(steps)
    return []


def with_steps(profiles, name, actions):
    """Return a copy of profiles where name holds exactly actions as its steps.

    Only the "actions" key is replaced, so a profile keeps any other fields it
    already stores and the profile JSON shape stays what it was.
    """
    updated = dict(profiles)
    profile = dict(updated.get(name) or {})
    profile["actions"] = copy.deepcopy(list(actions))
    updated[name] = profile
    return updated
