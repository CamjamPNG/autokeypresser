import threading
from dataclasses import dataclass, field

import pyautogui


@dataclass
class PressSettings:
    input_type: str = "mouse"  # "mouse" | "keyboard"
    mouse_button: str = "left"  # left / right / middle
    key: str = "a"
    modifiers: list = field(default_factory=list)  # pyautogui modifier names
    click_type: str = "single"  # single / double
    repeat_count: int = 1
    repeat_until_stopped: bool = True
    interval_seconds: float = 0.1
    use_fixed_position: bool = False
    fixed_x: int = 0
    fixed_y: int = 0
    actions: list = field(default_factory=list)


class PressEngine:
    """Presses the selected key or mouse button on a background thread."""

    def __init__(self, settings, on_status):
        self.settings = settings
        self.on_status = on_status
        self._stop_event = threading.Event()
        self._thread = None
        self.count = 0

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self._stop_event.clear()
        self.count = 0
        self._thread = threading.Thread(target=self._run, daemon=True, name="presser")
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        try:
            pyautogui.FAILSAFE = False
            interval = max(self.settings.interval_seconds, 0.001)
            limit = None if self.settings.repeat_until_stopped else max(
                self.settings.repeat_count, 0
            )
            done = 0
            cycles = 0
            actions = self.settings.actions or [self.settings]
            while not self._stop_event.is_set():
                for action in actions:
                    if self._stop_event.is_set():
                        break
                    self._press_action(action)
                    self.count += 1
                    done += 1
                    self.on_status(("status", self.count))
                    if self._stop_event.wait(interval):
                        break
                cycles += 1
                if limit is not None and cycles >= limit:
                    break
        finally:
            self.on_status(("done", self.count))

    def _press_once(self):
        self._press_action(self.settings)

    def _press_action(self, action):
        if isinstance(action, PressSettings):
            value = lambda name, default=None: getattr(action, name, default)
        else:
            value = lambda name, default=None: action.get(name, default)

        if value("input_type", "mouse") == "mouse":
            x, y = (
                (value("fixed_x", 0), value("fixed_y", 0))
                if value("use_fixed_position", False)
                else pyautogui.position()
            )
            if value("click_type", "single") == "double":
                pyautogui.click(x, y, clicks=2, interval=0.02, button=value("mouse_button", "left"))
            else:
                pyautogui.click(x, y, button=value("mouse_button", "left"))
        else:
            modifiers = value("modifiers", [])
            key = value("key", "a")
            if modifiers:
                pyautogui.hotkey(*modifiers, key)
            else:
                pyautogui.press(key)
            if value("click_type", "single") == "double":
                if modifiers:
                    pyautogui.hotkey(*modifiers, key)
                else:
                    pyautogui.press(key)
