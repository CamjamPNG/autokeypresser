import queue
import tkinter as tk
from tkinter import messagebox
import threading
import webbrowser

from . import keys as keymod
from .config import load_config, save_config
from .engine import PressEngine, PressSettings
from .profiles import load_profiles, save_profiles
from . import updater

APP_NAME = "AutoKeyPresser 1.4"

HOTKEY_MODS = [
    "None",
    "Ctrl",
    "Alt",
    "Shift",
    "Ctrl+Alt",
    "Ctrl+Shift",
    "Alt+Shift",
    "Ctrl+Alt+Shift",
]

HOTKEY_KEYS = (
    ["F%d" % i for i in range(1, 13)]
    + ["Insert", "Delete", "Home", "End", "Page Up", "Page Down",
       "Space", "Enter", "Tab", "Esc"]
    + [c.upper() for c in "abcdefghijklmnopqrstuvwxyz"]
    + list("0123456789")
)

_PYNPUT_SPECIAL = {
    "Insert": "<insert>",
    "Delete": "<delete>",
    "Home": "<home>",
    "End": "<end>",
    "Page Up": "<page_up>",
    "Page Down": "<page_down>",
    "Space": "<space>",
    "Enter": "<enter>",
    "Tab": "<tab>",
    "Esc": "<esc>",
}


def build_hotkey(mod, key):
    parts = []
    if mod and mod != "None":
        parts.extend("<%s>" % m.strip().lower() for m in mod.split("+"))
    if key in _PYNPUT_SPECIAL:
        parts.append(_PYNPUT_SPECIAL[key])
    elif key.startswith("F") and key[1:].isdigit():
        parts.append("<%s>" % key.lower())
    else:
        parts.append(key.lower())
    return "+".join(parts)


class AutoClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.resizable(False, False)

        self.config = load_config()
        self.settings = PressSettings()
        self.queue = queue.Queue()
        self.engine = None
        self.hotkey_listener = None
        self.pending_actions = []

        self._build_ui()
        self._apply_config()
        self._refresh_action_fields()
        self._update_hotkey_label()
        self._start_hotkey_listener()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(80, self._poll_queue)
        self.root.after(1200, self._check_for_updates)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = self.root

        # --- Click interval ------------------------------------------------
        interval = tk.LabelFrame(root, text="Click interval", padx=6, pady=4)
        interval.grid(row=0, column=0, columnspan=3, padx=6, pady=(6, 4), sticky="we")

        self.hours_var = tk.StringVar()
        self.mins_var = tk.StringVar()
        self.secs_var = tk.StringVar()
        self.ms_var = tk.StringVar()
        self.hold_mode_var = tk.BooleanVar()
        self.hold_duration_var = tk.StringVar(value="50")
        self.randomize_var = tk.BooleanVar()
        self.random_min_var = tk.StringVar(value="50")
        self.random_max_var = tk.StringVar(value="150")

        fields = [
            ("h", self.hours_var, 3),
            ("mins", self.mins_var, 3),
            ("secs", self.secs_var, 3),
            ("ms", self.ms_var, 4),
        ]
        for col, (label, var, width) in enumerate(fields):
            spin = tk.Spinbox(interval, from_=0, to=9999, textvariable=var, width=width)
            spin.grid(row=0, column=col * 2, padx=(0 if col == 0 else 8, 2), pady=2)
            tk.Label(interval, text=label).grid(row=0, column=col * 2 + 1, sticky="w")

        advanced = tk.LabelFrame(root, text="Advanced timing", padx=6, pady=3)
        advanced.grid(row=1, column=0, columnspan=3, padx=6, pady=3, sticky="we")
        tk.Checkbutton(advanced, text="Hold action for", variable=self.hold_mode_var).grid(
            row=0, column=0, sticky="w"
        )
        tk.Spinbox(advanced, from_=1, to=999999, textvariable=self.hold_duration_var, width=6).grid(
            row=0, column=1, padx=2
        )
        tk.Label(advanced, text="ms").grid(row=0, column=2, sticky="w")
        tk.Checkbutton(advanced, text="Random interval", variable=self.randomize_var).grid(
            row=0, column=3, padx=(12, 2), sticky="w"
        )
        tk.Label(advanced, text="min").grid(row=0, column=4)
        tk.Spinbox(advanced, from_=1, to=999999, textvariable=self.random_min_var, width=5).grid(
            row=0, column=5
        )
        tk.Label(advanced, text="max").grid(row=0, column=6, padx=(3, 0))
        tk.Spinbox(advanced, from_=1, to=999999, textvariable=self.random_max_var, width=5).grid(
            row=0, column=7
        )
        tk.Label(advanced, text="ms").grid(row=0, column=8, sticky="w")

        # --- Click options --------------------------------------------------
        opts = tk.LabelFrame(root, text="Click options", padx=6, pady=4)
        opts.grid(row=2, column=0, columnspan=3, padx=6, pady=4, sticky="we")

        left = tk.Frame(opts)
        left.grid(row=0, column=0, sticky="nw")
        right = tk.Frame(opts)
        right.grid(row=0, column=1, padx=(14, 0), sticky="nw")

        self.input_type_var = tk.StringVar(value="Mouse")
        tk.Label(left, text="Input type:").grid(row=0, column=0, sticky="e", pady=1)
        self.input_menu = tk.OptionMenu(
            left, self.input_type_var, "Mouse", "Keyboard",
            command=lambda _v: self._refresh_action_fields(),
        )
        self.input_menu.config(width=8)
        self.input_menu.grid(row=0, column=1, sticky="w", pady=1)

        self.mouse_button_var = tk.StringVar(value="Left")
        tk.Label(left, text="Mouse button:").grid(row=1, column=0, sticky="e", pady=1)
        self.mouse_menu = tk.OptionMenu(left, self.mouse_button_var, "Left", "Right", "Middle")
        self.mouse_menu.config(width=7)
        self.mouse_menu.grid(row=1, column=1, sticky="w", pady=1)

        self.key_var = tk.StringVar(value="A")
        tk.Label(left, text="Key:").grid(row=2, column=0, sticky="e", pady=1)
        self.key_menu = tk.OptionMenu(left, self.key_var, *keymod.DISPLAY_KEYS)
        self.key_menu.config(width=8)
        self.key_menu.grid(row=2, column=1, sticky="w", pady=1)

        tk.Label(left, text="Modifiers:").grid(row=3, column=0, sticky="ne", pady=1)
        mod_frame = tk.Frame(left)
        mod_frame.grid(row=3, column=1, sticky="w", pady=1)
        self.modifier_vars = {}
        self.modifier_boxes = {}
        for i, name in enumerate(keymod.MODIFIERS):
            var = tk.BooleanVar()
            box = tk.Checkbutton(mod_frame, text=name, variable=var)
            box.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 6))
            self.modifier_vars[name] = var
            self.modifier_boxes[name] = box

        self.click_type_var = tk.StringVar(value="Single")
        tk.Label(left, text="Click type:").grid(row=4, column=0, sticky="e", pady=1)
        tk.OptionMenu(left, self.click_type_var, "Single", "Double").grid(
            row=4, column=1, sticky="w", pady=1
        )

        self.repeat_mode_var = tk.StringVar(value="until")
        self.repeat_count_var = tk.StringVar(value="1")
        tk.Radiobutton(
            right, text="Repeat", variable=self.repeat_mode_var, value="count"
        ).grid(row=0, column=0, sticky="w", pady=1)
        tk.Spinbox(right, from_=1, to=999999, textvariable=self.repeat_count_var, width=5).grid(
            row=0, column=1, padx=(2, 2), pady=1
        )
        tk.Label(right, text="times").grid(row=0, column=2, sticky="w", pady=1)
        tk.Radiobutton(
            right, text="Repeat until stopped",
            variable=self.repeat_mode_var, value="until",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=1)

        # --- Cursor position ------------------------------------------------
        cursor = tk.LabelFrame(root, text="Cursor position", padx=6, pady=4)
        cursor.grid(row=3, column=0, columnspan=3, padx=6, pady=4, sticky="we")

        self.cursor_mode_var = tk.StringVar(value="current")
        self.x_var = tk.StringVar(value="0")
        self.y_var = tk.StringVar(value="0")

        tk.Radiobutton(
            cursor, text="Current location",
            variable=self.cursor_mode_var, value="current",
        ).grid(row=0, column=0, columnspan=8, sticky="w")

        row2 = tk.Frame(cursor)
        row2.grid(row=1, column=0, columnspan=8, sticky="w")
        tk.Radiobutton(
            row2, text="Pick location", variable=self.cursor_mode_var, value="pick"
        ).grid(row=0, column=0, sticky="w")
        tk.Button(row2, text="Pick location", command=self._pick_location).grid(
            row=0, column=1, padx=(6, 6)
        )
        tk.Label(row2, text="X:").grid(row=0, column=2)
        tk.Spinbox(row2, from_=-100000, to=100000, textvariable=self.x_var, width=7).grid(
            row=0, column=3
        )
        tk.Label(row2, text="Y:").grid(row=0, column=4, padx=(6, 0))
        tk.Spinbox(row2, from_=-100000, to=100000, textvariable=self.y_var, width=7).grid(
            row=0, column=5
        )

        # --- Bottom buttons -------------------------------------------------
        bottom = tk.Frame(root)
        bottom.grid(row=4, column=0, columnspan=3, padx=6, pady=(4, 4), sticky="we")
        bottom.columnconfigure(1, weight=1)

        tk.Button(bottom, text="Hotkey setting", command=self._open_hotkey_settings).grid(
            row=0, column=0, padx=(0, 4), pady=2
        )
        self.start_button = tk.Button(bottom, text="Start", width=14, command=self._toggle)
        self.start_button.grid(row=0, column=1, padx=4, pady=2)
        tk.Button(bottom, text="Help >>", command=self._open_help).grid(
            row=0, column=2, padx=(4, 0), pady=2
        )
        tk.Button(bottom, text="Profiles", command=self._open_profiles).grid(
            row=0, column=3, padx=(4, 0), pady=2
        )

        # --- Status bar ------------------------------------------------------
        self.status_var = tk.StringVar(value="Idle")
        tk.Label(
            root, textvariable=self.status_var, anchor="w",
            relief=tk.SUNKEN, bd=1,
        ).grid(row=5, column=0, columnspan=3, sticky="we", padx=6, pady=(0, 6))

    # ---------------------------------------------------------------- config
    def _apply_config(self):
        c = self.config
        self.input_type_var.set("Keyboard" if c.get("input_type") == "keyboard" else "Mouse")
        self.mouse_button_var.set(c.get("mouse_button", "left").title())
        display_key = next(
            (d for d, k in keymod.KEY_MAP if k == c.get("key")), "A"
        )
        self.key_var.set(display_key)
        for name, var in self.modifier_vars.items():
            var.set(keymod.os_modifier(name) in c.get("modifiers", []))
        self.click_type_var.set(c.get("click_type", "single").title())
        self.repeat_mode_var.set("until" if c.get("repeat_until_stopped", True) else "count")
        self.repeat_count_var.set(str(c.get("repeat_count", 1)))
        self.hours_var.set(str(c.get("hours", "0")))
        self.mins_var.set(str(c.get("mins", "0")))
        self.secs_var.set(str(c.get("secs", "0")))
        self.ms_var.set(str(c.get("ms", "100")))
        self.cursor_mode_var.set("pick" if c.get("use_fixed_position") else "current")
        self.x_var.set(str(c.get("x", "0")))
        self.y_var.set(str(c.get("y", "0")))
        self.hold_mode_var.set(c.get("hold_mode", False))
        self.hold_duration_var.set(str(c.get("hold_duration_ms", "50")))
        self.randomize_var.set(c.get("randomize_interval", False))
        self.random_min_var.set(str(c.get("random_min_ms", "50")))
        self.random_max_var.set(str(c.get("random_max_ms", "150")))

    def _collect_config(self):
        c = self.config
        c["input_type"] = "keyboard" if self.input_type_var.get() == "Keyboard" else "mouse"
        c["mouse_button"] = self.mouse_button_var.get().lower()
        c["key"] = keymod.display_to_key(self.key_var.get())
        c["modifiers"] = [keymod.os_modifier(n) for n, v in self.modifier_vars.items() if v.get()]
        c["click_type"] = self.click_type_var.get().lower()
        c["repeat_until_stopped"] = self.repeat_mode_var.get() == "until"
        c["repeat_count"] = int(self.repeat_count_var.get() or 1)
        c["hours"] = self.hours_var.get()
        c["mins"] = self.mins_var.get()
        c["secs"] = self.secs_var.get()
        c["ms"] = self.ms_var.get()
        c["use_fixed_position"] = self.cursor_mode_var.get() == "pick"
        c["x"] = self.x_var.get()
        c["y"] = self.y_var.get()
        c["hold_mode"] = self.hold_mode_var.get()
        c["hold_duration_ms"] = self.hold_duration_var.get()
        c["randomize_interval"] = self.randomize_var.get()
        c["random_min_ms"] = self.random_min_var.get()
        c["random_max_ms"] = self.random_max_var.get()
        return c

    # ------------------------------------------------------------- behaviors
    def _refresh_action_fields(self):
        is_keyboard = self.input_type_var.get() == "Keyboard"
        self.mouse_menu.config(state=tk.NORMAL if not is_keyboard else tk.DISABLED)
        self.key_menu.config(state=tk.NORMAL if is_keyboard else tk.DISABLED)
        state = tk.NORMAL if is_keyboard else tk.DISABLED
        for box in self.modifier_boxes.values():
            box.config(state=state)

    def _pick_location(self):
        import pyautogui

        x, y = pyautogui.position()
        self.x_var.set(str(int(x)))
        self.y_var.set(str(int(y)))
        self.cursor_mode_var.set("pick")

    def _collect_settings(self):
        s = self.settings
        s.input_type = "keyboard" if self.input_type_var.get() == "Keyboard" else "mouse"
        s.mouse_button = self.mouse_button_var.get().lower()
        s.key = keymod.display_to_key(self.key_var.get())
        s.modifiers = [keymod.os_modifier(n) for n, v in self.modifier_vars.items() if v.get()]
        s.click_type = self.click_type_var.get().lower()
        s.repeat_until_stopped = self.repeat_mode_var.get() == "until"
        s.repeat_count = int(self.repeat_count_var.get() or 1)
        h = int(self.hours_var.get() or 0)
        m = int(self.mins_var.get() or 0)
        sec = int(self.secs_var.get() or 0)
        ms = int(self.ms_var.get() or 0)
        s.interval_seconds = h * 3600 + m * 60 + sec + ms / 1000.0
        s.use_fixed_position = self.cursor_mode_var.get() == "pick"
        s.fixed_x = int(self.x_var.get() or 0)
        s.fixed_y = int(self.y_var.get() or 0)
        s.hold_mode = self.hold_mode_var.get()
        s.hold_duration_seconds = max(int(self.hold_duration_var.get() or 1) / 1000, 0.001)
        s.randomize_interval = self.randomize_var.get()
        s.random_min_seconds = max(int(self.random_min_var.get() or 1) / 1000, 0.001)
        s.random_max_seconds = max(int(self.random_max_var.get() or 1) / 1000, 0.001)
        if s.randomize_interval and s.random_max_seconds < s.random_min_seconds:
            raise ValueError("Random maximum must not be lower than minimum.")
        return s

    def _current_action(self):
        settings = self._collect_settings()
        return {
            "input_type": settings.input_type,
            "mouse_button": settings.mouse_button,
            "key": settings.key,
            "modifiers": list(settings.modifiers),
            "click_type": settings.click_type,
            "use_fixed_position": settings.use_fixed_position,
            "fixed_x": settings.fixed_x,
            "fixed_y": settings.fixed_y,
            "hold_mode": settings.hold_mode,
            "hold_duration_seconds": settings.hold_duration_seconds,
            "randomize_interval": settings.randomize_interval,
            "random_min_seconds": settings.random_min_seconds,
            "random_max_seconds": settings.random_max_seconds,
        }

    def _apply_action(self, action):
        self.input_type_var.set("Keyboard" if action.get("input_type") == "keyboard" else "Mouse")
        self.mouse_button_var.set(action.get("mouse_button", "left").title())
        self.key_var.set(next((d for d, k in keymod.KEY_MAP if k == action.get("key")), "A"))
        modifiers = action.get("modifiers", [])
        for name, var in self.modifier_vars.items():
            var.set(keymod.os_modifier(name) in modifiers)
        self.click_type_var.set(action.get("click_type", "single").title())
        self.cursor_mode_var.set("pick" if action.get("use_fixed_position") else "current")
        self.x_var.set(str(action.get("fixed_x", 0)))
        self.y_var.set(str(action.get("fixed_y", 0)))
        self.hold_mode_var.set(action.get("hold_mode", False))
        self.hold_duration_var.set(str(round(float(action.get("hold_duration_seconds", 0.05)) * 1000)))
        self.randomize_var.set(action.get("randomize_interval", False))
        self.random_min_var.set(str(round(float(action.get("random_min_seconds", 0.05)) * 1000)))
        self.random_max_var.set(str(round(float(action.get("random_max_seconds", 0.15)) * 1000)))
        self._refresh_action_fields()

    def _toggle(self):
        if self.engine and self.engine.running:
            self._stop()
        else:
            self._start()

    def _start(self):
        if self.engine and self.engine.running:
            return
        try:
            self._collect_settings()
        except ValueError:
            messagebox.showerror(APP_NAME, "Please enter valid numbers.")
            return
        self.engine = PressEngine(self.settings, on_status=self.queue.put)
        self.settings.actions = list(self.pending_actions)
        self.pending_actions = []
        self.engine.start()
        self._update_running_ui(True)
        self.status_var.set("Running - clicks: 0")

    def _stop(self):
        if self.engine:
            self.engine.stop()

    def _update_running_ui(self, running):
        if running:
            self.start_button.config(text="Stop")
        else:
            self._update_hotkey_label()

    def _poll_queue(self):
        try:
            while True:
                msg, value = self.queue.get_nowait()
                if msg == "status":
                    self.status_var.set("Running - clicks: %d" % value)
                elif msg == "done":
                    self.status_var.set("Stopped - clicks: %d" % value)
                    self._update_running_ui(False)
                elif msg == "update":
                    self._offer_update(value)
                elif msg == "update_downloaded":
                    self._finish_update(value)
                elif msg == "update_error":
                    self.status_var.set("Update failed")
                    messagebox.showerror(APP_NAME, "Could not download update:\n%s" % value)
        except queue.Empty:
            pass
        self.root.after(80, self._poll_queue)

    def _check_for_updates(self):
        def worker():
            try:
                release = updater.check_latest_release()
            except Exception:
                release = None
            if release:
                self.queue.put(("update", release))

        threading.Thread(target=worker, daemon=True, name="update-check").start()

    def _offer_update(self, release):
        version = release.get("tag_name", "new version")
        if not messagebox.askyesno(
            APP_NAME,
            "%s is available. Download and install it now?" % version,
        ):
            return
        installer = updater.installer_asset(release)
        if not installer:
            webbrowser.open(release.get("html_url", updater.RELEASES_PAGE))
            return

        self.status_var.set("Downloading update...")

        def worker():
            try:
                path = updater.download_installer(installer)
                self.queue.put(("update_downloaded", path))
            except Exception as exc:
                self.queue.put(("update_error", str(exc)))

        threading.Thread(target=worker, daemon=True, name="update-download").start()

    def _finish_update(self, path):
        if not messagebox.askyesno(
            APP_NAME,
            "The update is downloaded. Close AutoKeyPresser and run the installer?",
        ):
            self.status_var.set("Update downloaded")
            return
        updater.launch_installer(path)
        self._on_close()

    # ----------------------------------------------------------------- hotkey
    def _start_hotkey_listener(self):
        try:
            from pynput import keyboard

            combo = build_hotkey(self.config["hotkey_mod"], self.config["hotkey_key"])
            self.hotkey_listener = keyboard.GlobalHotKeys(
                {combo: self._toggle, "<f12>": self._emergency_stop}
            )
            self.hotkey_listener.start()
        except Exception as exc:
            self.hotkey_listener = None
            messagebox.showwarning(
                APP_NAME, "Global hotkey could not be registered:\n%s" % exc
            )

    def _stop_hotkey_listener(self):
        if self.hotkey_listener is not None:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
            self.hotkey_listener = None

    def _emergency_stop(self):
        if self.engine and self.engine.running:
            self.engine.stop()
            self.status_var.set("Emergency stop")

    def _update_hotkey_label(self):
        mod = self.config["hotkey_mod"]
        key = self.config["hotkey_key"]
        if mod and mod != "None":
            label = "%s+%s" % (mod, key)
        else:
            label = key
        self.start_button.config(text="Start (%s)" % label)

    def _open_hotkey_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Hotkey setting")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="Modifier:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        mod_var = tk.StringVar(value=self.config["hotkey_mod"])
        tk.OptionMenu(win, mod_var, *HOTKEY_MODS).grid(row=0, column=1, sticky="w", padx=4)

        tk.Label(win, text="Key:").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        key_var = tk.StringVar(value=self.config["hotkey_key"])
        tk.OptionMenu(win, key_var, *HOTKEY_KEYS).grid(row=1, column=1, sticky="w", padx=4)

        hint = tk.Label(
            win,
            text="The hotkey works even when this window\nis in the background.",
            justify="left",
        )
        hint.grid(row=2, column=0, columnspan=2, padx=4, pady=(2, 0))

        def save():
            self.config["hotkey_mod"] = mod_var.get()
            self.config["hotkey_key"] = key_var.get()
            save_config(self.config)
            self._stop_hotkey_listener()
            self._start_hotkey_listener()
            self._update_hotkey_label()
            win.destroy()

        btn = tk.Frame(win)
        btn.grid(row=3, column=0, columnspan=2, pady=(8, 6))
        tk.Button(btn, text="Save", width=8, command=save).pack(side="left", padx=4)
        tk.Button(btn, text="Cancel", width=8, command=win.destroy).pack(side="left", padx=4)

    # ------------------------------------------------------------------- help
    def _open_help(self):
        win = tk.Toplevel(self.root)
        win.title("Help")
        win.geometry("420x360")
        win.transient(self.root)

        text = tk.Text(win, wrap="word", padx=10, pady=10, relief=tk.FLAT)
        scroll = tk.Scrollbar(win, command=text.yview)
        text.config(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)

        text.insert(
            tk.END,
            APP_NAME
            + "\n"
            + "=" * len(APP_NAME)
            + """

How to use
----------
1. Set the delay between presses in "Click interval".
2. Under "Click options" choose Mouse or Keyboard.
   - Mouse: pick the button (Left/Right/Middle) and click type.
   - Keyboard: pick the key and any modifiers (Ctrl, Shift, Alt, Win/Cmd).
3. Set how many times to repeat, or choose "Repeat until stopped".
4. Under "Cursor position" click at the current mouse location, or
   pick a fixed screen position.
5. Press "Start" or the global hotkey to begin; press it again to stop.

Emergency stop
--------------
F12 always stops the active press immediately.

Global hotkey
-------------
The default hotkey is F6. Change it via "Hotkey setting". The hotkey
keeps working while other windows are focused.

Permissions
-----------
- Windows: works out of the box.
- Linux: run under an X11 session.
- macOS: grant the app "Accessibility" and "Input Monitoring"
  permission in System Settings > Privacy & Security.

Safety
------
A 0 ms interval runs extremely fast. Use the Stop button or the
F12 emergency key or the global hotkey to halt immediately. The counter on the status bar
shows how many presses have been sent.

The application is provided as-is. Use responsibly and only on
content you own or are authorized to automate.
""",
        )
        text.config(state=tk.DISABLED)

    # ------------------------------------------------------------------ close
    def _on_close(self):
        try:
            self._stop()
            try:
                save_config(self._collect_config())
            except ValueError:
                # Do not block shutdown because a field contains invalid text.
                pass
        finally:
            self._stop_hotkey_listener()
            self.root.destroy()

    def _open_profiles(self):
        profiles = load_profiles()
        win = tk.Toplevel(self.root)
        win.title("Profiles and sequences")
        win.resizable(False, False)
        win.transient(self.root)

        names = tk.StringVar(value=sorted(profiles))
        tk.Label(win, text="Saved profiles:").grid(row=0, column=0, padx=6, pady=(6, 2), sticky="w")
        listing = tk.Listbox(win, listvariable=names, height=7, width=28, exportselection=False)
        listing.grid(row=1, column=0, columnspan=2, padx=6, pady=2)
        name_var = tk.StringVar()
        tk.Label(win, text="Name:").grid(row=2, column=0, padx=6, sticky="e")
        tk.Entry(win, textvariable=name_var, width=24).grid(row=2, column=1, padx=6, pady=4)

        def selected_name():
            selected = listing.curselection()
            return listing.get(selected[0]) if selected else name_var.get().strip()

        def refresh():
            names.set(sorted(profiles))

        def save_current():
            name = name_var.get().strip()
            if not name:
                messagebox.showerror(APP_NAME, "Enter a profile name.", parent=win)
                return
            try:
                action = self._current_action()
            except ValueError:
                messagebox.showerror(APP_NAME, "Please enter valid values first.", parent=win)
                return
            profiles[name] = {"actions": [action]}
            save_profiles(profiles)
            refresh()

        def add_action():
            name = selected_name()
            if not name:
                messagebox.showerror(APP_NAME, "Select or enter a profile name.", parent=win)
                return
            try:
                action = self._current_action()
            except ValueError:
                messagebox.showerror(APP_NAME, "Please enter valid values first.", parent=win)
                return
            profiles.setdefault(name, {"actions": []}).setdefault("actions", []).append(action)
            save_profiles(profiles)
            name_var.set(name)
            refresh()

        def load_profile(run=False):
            name = selected_name()
            profile = profiles.get(name, {})
            actions = profile.get("actions", [])
            if not actions:
                return
            self._apply_action(actions[0])
            self.pending_actions = actions if len(actions) > 1 else []
            if run:
                self._start()

        def delete_profile():
            name = selected_name()
            if name in profiles:
                del profiles[name]
                save_profiles(profiles)
                refresh()

        buttons = tk.Frame(win)
        buttons.grid(row=3, column=0, columnspan=2, pady=6)
        for text, command in (
            ("Save current", save_current),
            ("Add action", add_action),
            ("Load", load_profile),
            ("Run sequence", lambda: load_profile(True)),
            ("Delete", delete_profile),
        ):
            tk.Button(buttons, text=text, command=command).pack(side="left", padx=2)
