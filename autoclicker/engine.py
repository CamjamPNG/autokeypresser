import math
import threading
import random
import time
from dataclasses import dataclass, field

import pyautogui

from .profiles import step_delay_seconds

# A deadline check can only be as precise as the clock it reads. Windows' CPython 3.12
# monotonic clock is GetTickCount64 at a 15.625 ms resolution, so this floor keeps the
# check honest on the sub-millisecond clocks and the real resolution is used elsewhere.
_MIN_DEADLINE_SLACK_SECONDS = 0.001


@dataclass
class PressSettings:
    input_type: str = "mouse"  # "mouse" | "keyboard" | "text"
    mouse_button: str = "left"  # left / right / middle
    key: str = "a"
    text: str = ""
    modifiers: list = field(default_factory=list)  # pyautogui modifier names
    click_type: str = "single"  # single / double
    repeat_count: int = 1
    repeat_until_stopped: bool = True
    interval_seconds: float = 0.1
    use_fixed_position: bool = False
    fixed_x: int = 0
    fixed_y: int = 0
    actions: list = field(default_factory=list)
    hold_mode: bool = False
    hold_duration_seconds: float = 0.05
    randomize_interval: bool = False
    random_min_seconds: float = 0.05
    random_max_seconds: float = 0.15
    start_delay_seconds: float = 0.0
    stop_after_seconds: float = 0.0


class PressEngine:
    """Presses the selected key or mouse button on a background thread."""

    def __init__(self, settings, on_status):
        self.settings = settings
        self.on_status = on_status
        self._stop_event = threading.Event()
        self._thread = None
        self.count = 0
        self._limit_reached = False
        self._captured_limit = 0.0
        self._deadline_slack = _MIN_DEADLINE_SLACK_SECONDS

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self._stop_event.clear()
        self.count = 0
        self._limit_reached = False
        self._thread = threading.Thread(target=self._run, daemon=True, name="presser")
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        try:
            pyautogui.FAILSAFE = False
            # PyAutoGUI defaults to a 100 ms pause after every call, which
            # caps the presser at roughly 10 actions per second.
            pyautogui.PAUSE = 0
            if not self._pre_roll():
                return
            interval = max(self.settings.interval_seconds, 0.001)
            limit = None if self.settings.repeat_until_stopped else max(
                self.settings.repeat_count, 0
            )
            deadline = self._deadline()
            done = 0
            cycles = 0
            actions = self.settings.actions or [self.settings]
            while not self._stop_event.is_set():
                if self._limit_hit(deadline):
                    break
                last_cycle = limit is not None and cycles + 1 >= limit
                for position, action in enumerate(actions):
                    if self._stop_event.is_set() or self._limit_hit(deadline):
                        break
                    self._press_action(action)
                    self.count += 1
                    done += 1
                    self.on_status(("status", self.count))
                    if last_cycle and position == len(actions) - 1:
                        # Nothing follows the final press, so waiting here would
                        # hold the run at "Running" for a pause that never ends.
                        break
                    if self._pause(self._next_interval(interval, action), deadline):
                        break
                if self._limit_reached:
                    break
                cycles += 1
                if limit is not None and cycles >= limit:
                    break
        finally:
            if self._limit_reached:
                # Report the value the deadline was taken from: the settings
                # object is shared with the UI, which may have been re-collected
                # mid-run, and a moved field must not rewrite what ended it.
                self.on_status(("limit", round(self._captured_limit)))
            self.on_status(("done", self.count))

    def _limit_seconds(self):
        try:
            return float(self.settings.stop_after_seconds or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _deadline(self):
        """The monotonic time the run must end, or None when it has no limit.

        The limit belongs to the until-stopped mode, so an exact-count run keeps
        running until its count however this is set. The clock starts when the
        actions begin rather than when Start is pressed: a start delay is time
        spent waiting, not time spent pressing.
        """
        self._captured_limit = 0.0
        if not self.settings.repeat_until_stopped:
            return None
        seconds = self._limit_seconds()
        if not math.isfinite(seconds) or seconds <= 0:
            return None
        self._captured_limit = seconds
        # The slack for the deadline comparisons is the resolution of the clock they
        # read: measured from the platform, not assumed.
        self._deadline_slack = max(
            _MIN_DEADLINE_SLACK_SECONDS, time.get_clock_info("monotonic").resolution
        )
        return time.monotonic() + seconds

    def _limit_hit(self, deadline):
        """True once the deadline has passed, remembering that the limit ended it.

        The comparison allows one tick of the clock it reads. A clock coarser than the
        deadline check assumed - Windows' CPython 3.12 monotonic clock is
        GetTickCount64 at 15.625 ms - reports the previous tick for a moment after the
        pause clamped to the deadline ends, and without that slack the run read "not
        reached" and sent the next action of the cycle as well. An action passes the
        deadline only when the platform's clock or wait error is coarser than the tick.
        """
        if deadline is None or time.monotonic() < deadline - self._deadline_slack:
            return False
        self._limit_reached = True
        return True

    def _pause(self, seconds, deadline):
        """Wait between actions, never past the deadline. True ends the run.

        The wait is clamped to the time left, so even a step delay or a
        randomized interval leaves at most the action already in flight past the
        deadline, and a stopped run never sits out a pause it will not use.
        """
        if deadline is not None:
            seconds = min(seconds, max(deadline - time.monotonic(), 0.0))
            if seconds <= 0:
                self._limit_reached = True
                return True
        if self._stop_event.wait(seconds):
            return True
        return self._limit_hit(deadline)

    def _pre_roll(self):
        """Wait out the start delay, reporting each whole second left.

        Returns False when a stop lands during the countdown, so no action is
        ever sent for that run.
        """
        remaining = max(
            float(getattr(self.settings, "start_delay_seconds", 0.0) or 0.0), 0.0
        )
        while remaining > 0:
            self.on_status(("countdown", int(math.ceil(remaining))))
            step = min(1.0, remaining)
            if self._stop_event.wait(step):
                return False
            remaining -= step
        return True

    def _press_once(self):
        self._press_action(self.settings)

    def _press_action(self, action):
        if isinstance(action, PressSettings):
            value = lambda name, default=None: getattr(action, name, default)
        else:
            value = lambda name, default=None: action.get(name, default)

        if value("input_type", "mouse") == "text":
            # pyautogui.write sends the whole string in one call, so one text
            # action costs exactly one interval.
            pyautogui.write(value("text", ""))
            return

        hold = value("hold_mode", False)
        hold_duration = max(float(value("hold_duration_seconds", 0.05)), 0.001)
        if value("input_type", "mouse") == "mouse":
            x, y = (
                (value("fixed_x", 0), value("fixed_y", 0))
                if value("use_fixed_position", False)
                else pyautogui.position()
            )
            if hold:
                pyautogui.moveTo(x, y)
                pyautogui.mouseDown(button=value("mouse_button", "left"))
                time.sleep(hold_duration)
                pyautogui.mouseUp(button=value("mouse_button", "left"))
            elif value("click_type", "single") == "double":
                pyautogui.click(x, y, clicks=2, interval=0.02, button=value("mouse_button", "left"))
            else:
                pyautogui.click(x, y, button=value("mouse_button", "left"))
        else:
            modifiers = value("modifiers", [])
            key = value("key", "a")
            if hold:
                for modifier in modifiers:
                    pyautogui.keyDown(modifier)
                pyautogui.keyDown(key)
                time.sleep(hold_duration)
                pyautogui.keyUp(key)
                for modifier in reversed(modifiers):
                    pyautogui.keyUp(modifier)
                return
            if modifiers:
                pyautogui.hotkey(*modifiers, key)
            else:
                pyautogui.press(key)
            if value("click_type", "single") == "double":
                if modifiers:
                    pyautogui.hotkey(*modifiers, key)
                else:
                    pyautogui.press(key)

    def _next_interval(self, default, action=None):
        """The pause after action: its own delay, else the global interval.

        A step's delay belongs to that step, so it also overrides a randomized
        global interval - a fixed pause is the whole reason to set one.
        """
        own = step_delay_seconds(action)
        if own is not None:
            return max(own, 0.001)
        if not self.settings.randomize_interval:
            return default
        low = max(self.settings.random_min_seconds, 0.001)
        high = max(self.settings.random_max_seconds, low)
        return random.uniform(low, high)
