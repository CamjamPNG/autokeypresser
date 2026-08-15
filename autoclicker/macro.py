import hashlib
import json
import platform
import threading
import time
from datetime import datetime, timezone

import pyautogui

from .keys import os_modifier

MACRO_MAGIC = b"AKPMACRO"
MACRO_VERSION = 1

_SPECIAL_KEYS = {
    "Key.space": "space",
    "Key.enter": "enter",
    "Key.tab": "tab",
    "Key.esc": "esc",
    "Key.backspace": "backspace",
    "Key.delete": "delete",
    "Key.insert": "insert",
    "Key.home": "home",
    "Key.end": "end",
    "Key.page_up": "pageup",
    "Key.page_down": "pagedown",
    "Key.up": "up",
    "Key.down": "down",
    "Key.left": "left",
    "Key.right": "right",
    "Key.shift": "shift",
    "Key.shift_r": "shift",
    "Key.ctrl": "ctrl",
    "Key.ctrl_r": "ctrl",
    "Key.alt": "alt",
    "Key.alt_r": "alt",
    "Key.cmd": "command" if platform.system() == "Darwin" else "win",
    "Key.cmd_r": "command" if platform.system() == "Darwin" else "win",
    "Key.caps_lock": "capslock",
    "Key.num_lock": "numlock",
    "Key.scroll_lock": "scrolllock",
    "Key.print_screen": "printscreen",
    "Key.pause": "pause",
    "Key.menu": "menu",
}
for _number in range(1, 21):
    _SPECIAL_KEYS["Key.f%d" % _number] = "f%d" % _number


class MacroFormatError(ValueError):
    """Raised when a file is not a valid AutoKeyPresser macro."""


def key_to_name(key):
    name = _SPECIAL_KEYS.get(str(key))
    if name:
        return name
    char = getattr(key, "char", None)
    return char.lower() if char else None


def _button_to_name(button):
    return str(button).removeprefix("Button.")


class MacroRecorder:
    def __init__(self):
        self.actions = []
        self.recording = False
        self._lock = threading.Lock()
        self._started_at = None
        self._keyboard_listener = None
        self._mouse_listener = None

    def start(self):
        self.stop()
        from pynput import keyboard as pynput_keyboard
        from pynput import mouse as pynput_mouse

        with self._lock:
            self.actions = []
            self._started_at = time.monotonic()
            self.recording = True
        self._keyboard_listener = pynput_keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._mouse_listener = pynput_mouse.Listener(
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self._keyboard_listener.start()
        self._mouse_listener.start()

    def stop(self):
        with self._lock:
            was_recording = self.recording
            self.recording = False
            actions = list(self.actions)
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()
        self._keyboard_listener = None
        self._mouse_listener = None
        if not was_recording:
            return actions

        previous = 0
        for action in actions:
            absolute = action.pop("_time_ms", 0)
            action["delay_ms"] = max(absolute - previous, 0)
            previous = absolute
        return actions

    def _record(self, action):
        with self._lock:
            if not self.recording or self._started_at is None:
                return
            action["_time_ms"] = int((time.monotonic() - self._started_at) * 1000)
            self.actions.append(action)

    def _on_key_press(self, key):
        name = key_to_name(key)
        if name:
            self._record({"type": "key", "action": "press", "key": name})

    def _on_key_release(self, key):
        name = key_to_name(key)
        if name:
            self._record({"type": "key", "action": "release", "key": name})

    def _on_click(self, x, y, button, pressed):
        self._record(
            {
                "type": "mouse",
                "action": "press" if pressed else "release",
                "button": _button_to_name(button),
                "x": int(x),
                "y": int(y),
            }
        )

    def _on_scroll(self, x, y, dx, dy):
        self._record(
            {"type": "scroll", "x": int(x), "y": int(y), "dx": int(dx), "dy": int(dy)}
        )


class MacroPlayer:
    def __init__(self, actions, repeat_count, repeat_until_stopped, on_status):
        self.actions = list(actions)
        self.repeat_count = repeat_count
        self.repeat_until_stopped = repeat_until_stopped
        self.on_status = on_status
        self.count = 0
        self._stop_event = threading.Event()
        self._thread = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self._stop_event.clear()
        self.count = 0
        self._thread = threading.Thread(target=self._run, daemon=True, name="macro-player")
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0
        cycles = 0
        limit = None if self.repeat_until_stopped else max(self.repeat_count, 1)
        try:
            while not self._stop_event.is_set():
                for action in self.actions:
                    if self._stop_event.wait(max(action.get("delay_ms", 0), 0) / 1000):
                        break
                    self._perform(action)
                    self.count += 1
                    self.on_status(("macro_status", self.count))
                cycles += 1
                if limit is not None and cycles >= limit:
                    break
        finally:
            self.on_status(("macro_done", self.count))

    @staticmethod
    def _perform(action):
        action_type = action.get("type")
        if action_type == "key":
            if action.get("action") == "press":
                pyautogui.keyDown(action["key"])
            else:
                pyautogui.keyUp(action["key"])
        elif action_type == "mouse":
            x, y = action.get("x"), action.get("y")
            pyautogui.moveTo(x, y)
            method = pyautogui.mouseDown if action.get("action") == "press" else pyautogui.mouseUp
            method(button=action.get("button", "left"))
        elif action_type == "scroll":
            pyautogui.scroll(action.get("dy", 0), action.get("x"), action.get("y"))


def save_macro(actions, path, name="Shared macro"):
    payload = {
        "format": "AutoKeyPresser Macro",
        "version": MACRO_VERSION,
        "name": name,
        "recorded": datetime.now(timezone.utc).isoformat(),
        "actions": actions,
    }
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    content = MACRO_MAGIC + bytes([MACRO_VERSION]) + data
    checksum = hashlib.sha256(content).hexdigest().encode("ascii")
    with open(path, "wb") as handle:
        handle.write(content + b"\n" + checksum)


def load_macro(path):
    with open(path, "rb") as handle:
        raw = handle.read()
    if len(raw) < len(MACRO_MAGIC) + 1 + 1 + 64:
        raise MacroFormatError("The file is too small to be an AutoKeyPresser macro.")
    content, checksum = raw[:-65], raw[-64:]
    if hashlib.sha256(content).hexdigest().encode("ascii") != checksum:
        raise MacroFormatError("Macro checksum mismatch; the file may be corrupt or modified.")
    if not content.startswith(MACRO_MAGIC):
        raise MacroFormatError("This is not an AutoKeyPresser macro file.")
    if content[len(MACRO_MAGIC)] != MACRO_VERSION:
        raise MacroFormatError("This macro version is not supported by this AutoKeyPresser build.")
    try:
        payload = json.loads(content[len(MACRO_MAGIC) + 1 :].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MacroFormatError("The macro payload is invalid.") from exc
    if payload.get("format") != "AutoKeyPresser Macro" or not isinstance(payload.get("actions"), list):
        raise MacroFormatError("This is not an AutoKeyPresser macro file.")
    return payload
