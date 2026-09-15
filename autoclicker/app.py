import queue
import sys
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk
import threading
import webbrowser

from . import keys as keymod
from .config import load_config, save_config
from .engine import PressEngine, PressSettings
from . import macro, themes
from .profiles import load_profiles, save_profiles
from . import updater

APP_NAME = "AutoKeyPresser 1.6"


def _mix_color(color, other, amount):
    """Blend two #RRGGBB colours without adding a UI dependency."""
    color = color.lstrip("#")
    other = other.lstrip("#")
    values = []
    for index in (0, 2, 4):
        start = int(color[index:index + 2], 16)
        end = int(other[index:index + 2], 16)
        values.append(round(start + (end - start) * amount))
    return "#%02x%02x%02x" % tuple(values)


class ToggleSwitch(tk.Canvas):
    """Small keyboard-accessible switch used by the advanced timing controls."""

    def __init__(self, master, variable, command=None, **kwargs):
        super().__init__(
            master,
            width=44,
            height=24,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=1,
            **kwargs,
        )
        self.variable = variable
        self.command = command
        self.colors = {}
        self.bind("<Button-1>", self._toggle)
        self.bind("<space>", self._toggle)
        self.bind("<Return>", self._toggle)
        self.variable.trace_add("write", lambda *_args: self._draw())

    def set_colors(self, panel, accent, border, knob):
        self.colors = {
            "panel": panel,
            "accent": accent,
            "border": border,
            "knob": knob,
        }
        self.configure(bg=panel)
        self._draw()

    def _toggle(self, _event=None):
        if str(self.cget("state")) == tk.DISABLED:
            return "break"
        self.variable.set(not self.variable.get())
        if self.command:
            self.command()
        return "break"

    def _draw(self):
        if not self.colors:
            return
        self.delete("all")
        enabled = bool(self.variable.get())
        track = self.colors["accent"] if enabled else self.colors["border"]
        x0, y0, x1, y1, radius = 2, 3, 42, 21, 9
        self.create_rectangle(x0 + radius, y0, x1 - radius, y1, fill=track, outline=track)
        self.create_oval(x0, y0, x0 + radius * 2, y1, fill=track, outline=track)
        self.create_oval(x1 - radius * 2, y0, x1, y1, fill=track, outline=track)
        knob_x = 30 if enabled else 12
        self.create_oval(
            knob_x - 7,
            5,
            knob_x + 7,
            19,
            fill=self.colors["knob"],
            outline=self.colors["knob"],
        )

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
        width, height = 1040, 780
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max((screen_width - width) // 2, 0)
        y = max((screen_height - height) // 2, 0)
        self.root.geometry("%dx%d+%d+%d" % (width, height, x, y))
        self.root.minsize(960, 720)
        self.root.resizable(True, True)

        self.config = load_config()
        self.settings = PressSettings()
        self.queue = queue.Queue()
        self.engine = None
        self.hotkey_listener = None
        self.pending_actions = []
        self.recorder = None
        self.last_macro = []
        self.macro_player = None
        self.current_theme = self._theme_for_name(self.config.get("theme", "Aurora"))
        self.style = ttk.Style(self.root)
        self._switches = []
        self._configure_styles(self.current_theme["colors"])
        self.root.configure(bg=self.current_theme["colors"]["window"])

        self._build_ui()
        self._apply_config()
        self._refresh_action_fields()
        self._refresh_timing_fields()
        self._refresh_repeat_fields()
        self._refresh_cursor_fields()
        self._update_hotkey_label()
        self._start_hotkey_listener()
        self._load_macro_from_args()
        if not self._load_theme_from_args():
            self._apply_theme(self.config.get("theme", "Aurora"))

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(80, self._poll_queue)
        self.root.after(1200, self._check_for_updates)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = self.root

        # Variables live here so the interface can be re-themed without being rebuilt.
        self.hours_var = tk.StringVar(value="0")
        self.mins_var = tk.StringVar(value="0")
        self.secs_var = tk.StringVar(value="0")
        self.ms_var = tk.StringVar(value="100")
        self.hold_mode_var = tk.BooleanVar()
        self.hold_duration_var = tk.StringVar(value="50")
        self.randomize_var = tk.BooleanVar()
        self.random_min_var = tk.StringVar(value="50")
        self.random_max_var = tk.StringVar(value="150")
        self.input_type_var = tk.StringVar(value="Mouse")
        self.mouse_button_var = tk.StringVar(value="Left")
        self.key_var = tk.StringVar(value="A")
        self.click_type_var = tk.StringVar(value="Single")
        self.repeat_mode_var = tk.StringVar(value="until")
        self.repeat_count_var = tk.StringVar(value="1")
        self.cursor_mode_var = tk.StringVar(value="current")
        self.x_var = tk.StringVar(value="0")
        self.y_var = tk.StringVar(value="0")
        self.theme_var = tk.StringVar(value=self.config.get("theme", "Aurora"))
        self.macro_status_var = tk.StringVar(value="No macro loaded")
        self.status_var = tk.StringVar(value="Ready")
        self.run_state_var = tk.StringVar(value="READY")
        self.summary_var = tk.StringVar(value="Left click every 100 ms")

        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)

        shell = ttk.Frame(root, style="App.TFrame", padding=(28, 20, 28, 16))
        shell.grid(row=0, column=0, sticky="nsew")
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        # Header -------------------------------------------------------------
        header = ttk.Frame(shell, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header.grid_columnconfigure(1, weight=1)

        self.brand_canvas = tk.Canvas(
            header,
            width=46,
            height=46,
            highlightthickness=0,
            bd=0,
        )
        self.brand_canvas.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 13))

        ttk.Label(header, text="AutoKeyPresser", style="Title.TLabel").grid(
            row=0, column=1, sticky="sw"
        )
        ttk.Label(
            header,
            text="Precision automation, without the clutter.",
            style="Muted.TLabel",
        ).grid(row=1, column=1, sticky="nw", pady=(1, 0))

        header_actions = ttk.Frame(header, style="App.TFrame")
        header_actions.grid(row=0, column=2, rowspan=2, sticky="e")
        ttk.Label(header_actions, text="F12 emergency stop", style="Quiet.TLabel").grid(
            row=0, column=0, padx=(0, 12)
        )
        ttk.Button(
            header_actions,
            text="Profiles",
            style="Ghost.TButton",
            command=self._open_profiles,
        ).grid(row=0, column=1, padx=4)
        ttk.Button(
            header_actions,
            text="Appearance",
            style="Ghost.TButton",
            command=self._open_theme_settings,
        ).grid(row=0, column=2, padx=4)
        ttk.Button(
            header_actions,
            text="Help",
            style="Ghost.TButton",
            command=self._open_help,
        ).grid(row=0, column=3, padx=(4, 0))

        # Main workspace -----------------------------------------------------
        workspace = ttk.Frame(shell, style="App.TFrame")
        workspace.grid(row=1, column=0, sticky="nsew")
        workspace.grid_rowconfigure(0, weight=1)
        workspace.grid_columnconfigure(0, weight=3, uniform="workspace")
        workspace.grid_columnconfigure(1, weight=2, uniform="workspace")

        left_column = ttk.Frame(workspace, style="App.TFrame")
        left_column.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        left_column.grid_columnconfigure(0, weight=1)
        left_column.grid_rowconfigure(0, weight=1)
        left_column.grid_rowconfigure(1, weight=1)

        right_column = ttk.Frame(workspace, style="App.TFrame")
        right_column.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        right_column.grid_columnconfigure(0, weight=1)
        right_column.grid_rowconfigure(0, weight=1)

        # Action card --------------------------------------------------------
        action = ttk.Frame(left_column, style="Card.TFrame", padding=(20, 18))
        action.grid(row=0, column=0, sticky="nsew", pady=(0, 9))
        action.grid_columnconfigure(0, weight=1)

        action_header = ttk.Frame(action, style="Panel.TFrame")
        action_header.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        action_header.grid_columnconfigure(0, weight=1)
        ttk.Label(action_header, text="Action", style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            action_header,
            text="Choose what AutoKeyPresser sends",
            style="CardMuted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        mode = ttk.Frame(action_header, style="Segment.TFrame", padding=2)
        mode.grid(row=0, column=1, rowspan=2, sticky="e")
        ttk.Radiobutton(
            mode,
            text="Mouse",
            variable=self.input_type_var,
            value="Mouse",
            style="Segment.TRadiobutton",
            command=self._refresh_action_fields,
        ).grid(row=0, column=0)
        ttk.Radiobutton(
            mode,
            text="Keyboard",
            variable=self.input_type_var,
            value="Keyboard",
            style="Segment.TRadiobutton",
            command=self._refresh_action_fields,
        ).grid(row=0, column=1)

        action_fields = ttk.Frame(action, style="Panel.TFrame")
        action_fields.grid(row=1, column=0, sticky="ew")
        for column in range(3):
            action_fields.grid_columnconfigure(column, weight=1)

        ttk.Label(action_fields, text="MOUSE BUTTON", style="FieldLabel.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 10)
        )
        ttk.Label(action_fields, text="KEY", style="FieldLabel.TLabel").grid(
            row=0, column=1, sticky="w", padx=10
        )
        ttk.Label(action_fields, text="PRESS TYPE", style="FieldLabel.TLabel").grid(
            row=0, column=2, sticky="w", padx=(10, 0)
        )

        self.mouse_menu = ttk.Combobox(
            action_fields,
            textvariable=self.mouse_button_var,
            values=("Left", "Right", "Middle"),
            state="readonly",
        )
        self.mouse_menu.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(6, 0))
        self.key_menu = ttk.Combobox(
            action_fields,
            textvariable=self.key_var,
            values=keymod.DISPLAY_KEYS,
            state="readonly",
        )
        self.key_menu.grid(row=1, column=1, sticky="ew", padx=10, pady=(6, 0))
        self.click_type_menu = ttk.Combobox(
            action_fields,
            textvariable=self.click_type_var,
            values=("Single", "Double"),
            state="readonly",
        )
        self.click_type_menu.grid(row=1, column=2, sticky="ew", padx=(10, 0), pady=(6, 0))

        ttk.Label(action_fields, text="MODIFIERS", style="FieldLabel.TLabel").grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(17, 6)
        )
        modifier_row = ttk.Frame(action_fields, style="Panel.TFrame")
        modifier_row.grid(row=3, column=0, columnspan=3, sticky="w")
        self.modifier_vars = {}
        self.modifier_boxes = {}
        for index, name in enumerate(keymod.MODIFIERS):
            var = tk.BooleanVar()
            box = ttk.Checkbutton(
                modifier_row,
                text=name,
                variable=var,
                style="Chip.TCheckbutton",
            )
            box.grid(row=0, column=index, padx=(0, 7))
            self.modifier_vars[name] = var
            self.modifier_boxes[name] = box

        # Timing card --------------------------------------------------------
        timing = ttk.Frame(left_column, style="Card.TFrame", padding=(20, 18))
        timing.grid(row=1, column=0, sticky="nsew", pady=(9, 0))
        timing.grid_columnconfigure(0, weight=1)

        timing_header = ttk.Frame(timing, style="Panel.TFrame")
        timing_header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        timing_header.grid_columnconfigure(0, weight=1)
        ttk.Label(timing_header, text="Timing", style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            timing_header,
            text="Set the pace, then add natural variation if needed",
            style="CardMuted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Label(timing_header, text="INTERVAL", style="Badge.TLabel").grid(
            row=0, column=1, rowspan=2, sticky="e"
        )

        interval_row = ttk.Frame(timing, style="Panel.TFrame")
        interval_row.grid(row=1, column=0, sticky="ew")
        interval_fields = [
            ("HOURS", self.hours_var, 9999),
            ("MINUTES", self.mins_var, 9999),
            ("SECONDS", self.secs_var, 9999),
            ("MILLISECONDS", self.ms_var, 999999),
        ]
        for column, (label, variable, maximum) in enumerate(interval_fields):
            interval_row.grid_columnconfigure(column, weight=1)
            field = ttk.Frame(interval_row, style="Panel.TFrame")
            field.grid(
                row=0,
                column=column,
                sticky="ew",
                padx=(0 if column == 0 else 6, 0 if column == 3 else 6),
            )
            ttk.Label(field, text=label, style="FieldLabel.TLabel").grid(
                row=0, column=0, sticky="w", pady=(0, 6)
            )
            ttk.Spinbox(
                field,
                from_=0,
                to=maximum,
                textvariable=variable,
                width=7,
            ).grid(row=1, column=0, sticky="ew")
            field.grid_columnconfigure(0, weight=1)

        ttk.Separator(timing, orient="horizontal").grid(
            row=2, column=0, sticky="ew", pady=(16, 14)
        )
        advanced_row = ttk.Frame(timing, style="Panel.TFrame")
        advanced_row.grid(row=3, column=0, sticky="ew")
        advanced_row.grid_columnconfigure(0, weight=1)
        advanced_row.grid_columnconfigure(1, weight=1)

        hold_group = ttk.Frame(advanced_row, style="Panel.TFrame")
        hold_group.grid(row=0, column=0, sticky="w")
        hold_switch = ToggleSwitch(
            hold_group,
            self.hold_mode_var,
            command=self._refresh_timing_fields,
        )
        hold_switch.grid(row=0, column=0, rowspan=2, padx=(0, 9))
        self._switches.append(hold_switch)
        ttk.Label(hold_group, text="Hold action", style="CardLabel.TLabel").grid(
            row=0, column=1, sticky="w"
        )
        hold_input = ttk.Frame(hold_group, style="Panel.TFrame")
        hold_input.grid(row=1, column=1, sticky="w", pady=(3, 0))
        self.hold_duration_spin = ttk.Spinbox(
            hold_input,
            from_=1,
            to=999999,
            textvariable=self.hold_duration_var,
            width=7,
        )
        self.hold_duration_spin.grid(row=0, column=0)
        ttk.Label(hold_input, text=" ms", style="CardMuted.TLabel").grid(row=0, column=1)

        random_group = ttk.Frame(advanced_row, style="Panel.TFrame")
        random_group.grid(row=0, column=1, sticky="e")
        random_switch = ToggleSwitch(
            random_group,
            self.randomize_var,
            command=self._refresh_timing_fields,
        )
        random_switch.grid(row=0, column=0, rowspan=2, padx=(0, 9))
        self._switches.append(random_switch)
        ttk.Label(random_group, text="Natural variation", style="CardLabel.TLabel").grid(
            row=0, column=1, columnspan=4, sticky="w"
        )
        self.random_min_spin = ttk.Spinbox(
            random_group,
            from_=1,
            to=999999,
            textvariable=self.random_min_var,
            width=6,
        )
        self.random_min_spin.grid(row=1, column=1, pady=(3, 0))
        ttk.Label(random_group, text=" to ", style="CardMuted.TLabel").grid(row=1, column=2)
        self.random_max_spin = ttk.Spinbox(
            random_group,
            from_=1,
            to=999999,
            textvariable=self.random_max_var,
            width=6,
        )
        self.random_max_spin.grid(row=1, column=3, pady=(3, 0))
        ttk.Label(random_group, text=" ms", style="CardMuted.TLabel").grid(row=1, column=4)

        # Run card -----------------------------------------------------------
        run = ttk.Frame(right_column, style="Card.TFrame", padding=(22, 20))
        run.grid(row=0, column=0, sticky="nsew")
        run.grid_columnconfigure(0, weight=1)
        run.grid_rowconfigure(7, weight=1)

        run_header = ttk.Frame(run, style="Panel.TFrame")
        run_header.grid(row=0, column=0, sticky="ew")
        run_header.grid_columnconfigure(0, weight=1)
        ttk.Label(run_header, text="Run plan", style="CardTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            run_header,
            text="Review how and where it repeats",
            style="CardMuted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Label(run_header, textvariable=self.run_state_var, style="State.TLabel").grid(
            row=0, column=1, rowspan=2, sticky="e"
        )

        ttk.Label(run, text="REPEAT", style="FieldLabel.TLabel").grid(
            row=1, column=0, sticky="w", pady=(22, 8)
        )
        repeat_mode = ttk.Frame(run, style="Segment.TFrame", padding=2)
        repeat_mode.grid(row=2, column=0, sticky="ew")
        repeat_mode.grid_columnconfigure(0, weight=1)
        repeat_mode.grid_columnconfigure(1, weight=1)
        ttk.Radiobutton(
            repeat_mode,
            text="Until stopped",
            variable=self.repeat_mode_var,
            value="until",
            style="WideSegment.TRadiobutton",
            command=self._refresh_repeat_fields,
        ).grid(row=0, column=0, sticky="ew")
        ttk.Radiobutton(
            repeat_mode,
            text="Exact count",
            variable=self.repeat_mode_var,
            value="count",
            style="WideSegment.TRadiobutton",
            command=self._refresh_repeat_fields,
        ).grid(row=0, column=1, sticky="ew")

        count_row = ttk.Frame(run, style="Panel.TFrame")
        count_row.grid(row=3, column=0, sticky="ew", pady=(9, 0))
        ttk.Label(count_row, text="Number of actions", style="CardMuted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        count_row.grid_columnconfigure(0, weight=1)
        self.repeat_count_spin = ttk.Spinbox(
            count_row,
            from_=1,
            to=999999,
            textvariable=self.repeat_count_var,
            width=10,
        )
        self.repeat_count_spin.grid(row=0, column=1, sticky="e")

        ttk.Separator(run, orient="horizontal").grid(
            row=4, column=0, sticky="ew", pady=(18, 16)
        )
        ttk.Label(run, text="CURSOR POSITION", style="FieldLabel.TLabel").grid(
            row=5, column=0, sticky="w", pady=(0, 8)
        )
        cursor_mode = ttk.Frame(run, style="Segment.TFrame", padding=2)
        cursor_mode.grid(row=6, column=0, sticky="ew")
        cursor_mode.grid_columnconfigure(0, weight=1)
        cursor_mode.grid_columnconfigure(1, weight=1)
        self.cursor_live_radio = ttk.Radiobutton(
            cursor_mode,
            text="Live cursor",
            variable=self.cursor_mode_var,
            value="current",
            style="WideSegment.TRadiobutton",
            command=self._refresh_cursor_fields,
        )
        self.cursor_live_radio.grid(row=0, column=0, sticky="ew")
        self.cursor_fixed_radio = ttk.Radiobutton(
            cursor_mode,
            text="Fixed point",
            variable=self.cursor_mode_var,
            value="pick",
            style="WideSegment.TRadiobutton",
            command=self._refresh_cursor_fields,
        )
        self.cursor_fixed_radio.grid(row=0, column=1, sticky="ew")

        self.fixed_row = ttk.Frame(run, style="Panel.TFrame")
        self.fixed_row.grid(row=7, column=0, sticky="new", pady=(10, 0))
        self.fixed_row.grid_columnconfigure(4, weight=1)
        self.pick_button = ttk.Button(
            self.fixed_row,
            text="Use cursor",
            style="Secondary.TButton",
            command=self._pick_location,
        )
        self.pick_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Label(self.fixed_row, text="X", style="CardMuted.TLabel").grid(row=0, column=1)
        self.x_spin = ttk.Spinbox(
            self.fixed_row,
            from_=-100000,
            to=100000,
            textvariable=self.x_var,
            width=7,
        )
        self.x_spin.grid(row=0, column=2, padx=(5, 8))
        ttk.Label(self.fixed_row, text="Y", style="CardMuted.TLabel").grid(row=0, column=3)
        self.y_spin = ttk.Spinbox(
            self.fixed_row,
            from_=-100000,
            to=100000,
            textvariable=self.y_var,
            width=7,
        )
        self.y_spin.grid(row=0, column=4, padx=(5, 0), sticky="w")

        summary = ttk.Frame(run, style="Inset.TFrame", padding=(14, 12))
        summary.grid(row=8, column=0, sticky="ew", pady=(18, 14))
        summary.grid_columnconfigure(1, weight=1)
        ttk.Label(summary, text="◆", style="AccentGlyph.TLabel").grid(
            row=0, column=0, sticky="n", padx=(0, 10)
        )
        ttk.Label(
            summary,
            textvariable=self.summary_var,
            style="Summary.TLabel",
            wraplength=260,
            justify="left",
        ).grid(row=0, column=1, sticky="w")

        self.start_button = ttk.Button(
            run,
            text="Start automation",
            style="Primary.TButton",
            command=self._toggle,
        )
        self.start_button.grid(row=9, column=0, sticky="ew")
        hotkey_row = ttk.Frame(run, style="Panel.TFrame")
        hotkey_row.grid(row=10, column=0, sticky="ew", pady=(9, 0))
        hotkey_row.grid_columnconfigure(1, weight=1)
        ttk.Button(
            hotkey_row,
            text="Change hotkey",
            style="Link.TButton",
            command=self._open_hotkey_settings,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            hotkey_row,
            text="F12 always stops instantly",
            style="CardMuted.TLabel",
        ).grid(row=0, column=1, sticky="e")

        # Macro bar ----------------------------------------------------------
        macros = ttk.Frame(shell, style="Card.TFrame", padding=(18, 14))
        macros.grid(row=2, column=0, sticky="ew", pady=(18, 0))
        macros.grid_columnconfigure(1, weight=1)
        macro_title = ttk.Frame(macros, style="Panel.TFrame")
        macro_title.grid(row=0, column=0, sticky="w", padx=(0, 18))
        ttk.Label(macro_title, text="Macro studio", style="CardTitleSmall.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            macro_title,
            textvariable=self.macro_status_var,
            style="CardMuted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        macro_actions = ttk.Frame(macros, style="Panel.TFrame")
        macro_actions.grid(row=0, column=2, sticky="e")
        self.record_button = ttk.Button(
            macro_actions,
            text="Record",
            style="Record.TButton",
            command=self._toggle_record,
        )
        self.record_button.grid(row=0, column=0, padx=4)
        ttk.Button(
            macro_actions,
            text="Stop",
            style="Ghost.TButton",
            command=self._stop_record,
        ).grid(row=0, column=1, padx=4)
        self.play_macro_button = ttk.Button(
            macro_actions,
            text="Play",
            style="Secondary.TButton",
            command=self._play_macro,
        )
        self.play_macro_button.grid(row=0, column=2, padx=4)
        ttk.Button(
            macro_actions,
            text="Load .akp",
            style="Ghost.TButton",
            command=self._load_macro,
        ).grid(row=0, column=3, padx=4)
        ttk.Button(
            macro_actions,
            text="Save",
            style="Ghost.TButton",
            command=self._save_macro,
        ).grid(row=0, column=4, padx=(4, 0))

        # Footer -------------------------------------------------------------
        footer = ttk.Frame(shell, style="App.TFrame")
        footer.grid(row=3, column=0, sticky="ew", pady=(13, 0))
        footer.grid_columnconfigure(1, weight=1)
        self.status_dot = tk.Canvas(
            footer,
            width=12,
            height=12,
            highlightthickness=0,
            bd=0,
        )
        self.status_dot.grid(row=0, column=0, padx=(1, 7))
        ttk.Label(footer, textvariable=self.status_var, style="Muted.TLabel").grid(
            row=0, column=1, sticky="w"
        )
        ttk.Label(footer, text="v1.6  •  local by design", style="Quiet.TLabel").grid(
            row=0, column=2, sticky="e"
        )

        watched = (
            self.input_type_var,
            self.mouse_button_var,
            self.key_var,
            self.click_type_var,
            self.repeat_mode_var,
            self.repeat_count_var,
            self.hours_var,
            self.mins_var,
            self.secs_var,
            self.ms_var,
            self.cursor_mode_var,
            self.x_var,
            self.y_var,
            self.hold_mode_var,
            self.hold_duration_var,
            self.randomize_var,
            self.random_min_var,
            self.random_max_var,
        )
        for variable in watched:
            variable.trace_add("write", lambda *_args: self._update_summary())
        for variable in self.modifier_vars.values():
            variable.trace_add("write", lambda *_args: self._update_summary())
        self.status_var.trace_add("write", lambda *_args: self._update_status_visual())
        self._draw_brand_mark()
        self._update_summary()
        self._update_status_visual()

    def _theme_for_name(self, name):
        try:
            return themes.make_theme(name)
        except KeyError:
            try:
                return themes.load_user_theme(name)
            except (OSError, ValueError):
                fallback = "Aurora" if "Aurora" in themes.theme_names() else "Midnight"
                return themes.make_theme(fallback)

    def _configure_styles(self, colors):
        """Build a small design system on top of ttk's portable clam theme."""
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        available = set(tkfont.families(self.root))
        body_family = next(
            (name for name in ("Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica") if name in available),
            "TkDefaultFont",
        )
        display_family = next(
            (name for name in ("Segoe UI Variable Display", "Segoe UI", "SF Pro Display", "Helvetica") if name in available),
            body_family,
        )
        self.body_font = body_family
        self.display_font = display_family

        window = colors["window"]
        panel = colors["panel"]
        field = colors["input"]
        text = colors["text"]
        muted = colors["muted_text"]
        accent = colors["accent"]
        accent_text = colors["accent_text"]
        border = colors["border"]
        disabled = colors["disabled"]
        danger = colors["danger"]
        success = colors.get("success", "#42d392")
        panel_alt = _mix_color(panel, field, 0.52)
        accent_soft = _mix_color(panel, accent, 0.18)
        accent_hover = _mix_color(accent, "#ffffff", 0.10)
        accent_pressed = _mix_color(accent, "#000000", 0.12)
        danger_hover = _mix_color(danger, "#ffffff", 0.10)

        self.style.configure(".", font=(body_family, 10))
        self.style.configure("App.TFrame", background=window)
        self.style.configure("Panel.TFrame", background=panel)
        self.style.configure(
            "Card.TFrame",
            background=panel,
            relief="solid",
            borderwidth=1,
            bordercolor=border,
            lightcolor=border,
            darkcolor=border,
        )
        self.style.configure("Inset.TFrame", background=panel_alt)
        self.style.configure("Segment.TFrame", background=field)

        self.style.configure("TLabel", background=window, foreground=text)
        self.style.configure(
            "Title.TLabel",
            background=window,
            foreground=text,
            font=(display_family, 21, "bold"),
        )
        self.style.configure(
            "Muted.TLabel", background=window, foreground=muted, font=(body_family, 9)
        )
        self.style.configure(
            "Quiet.TLabel",
            background=window,
            foreground=_mix_color(muted, window, 0.15),
            font=(body_family, 9),
        )
        self.style.configure(
            "CardTitle.TLabel",
            background=panel,
            foreground=text,
            font=(display_family, 15, "bold"),
        )
        self.style.configure(
            "CardTitleSmall.TLabel",
            background=panel,
            foreground=text,
            font=(display_family, 12, "bold"),
        )
        self.style.configure(
            "CardLabel.TLabel",
            background=panel,
            foreground=text,
            font=(body_family, 9, "bold"),
        )
        self.style.configure(
            "CardMuted.TLabel", background=panel, foreground=muted, font=(body_family, 9)
        )
        self.style.configure(
            "FieldLabel.TLabel",
            background=panel,
            foreground=muted,
            font=(body_family, 8, "bold"),
        )
        self.style.configure(
            "Badge.TLabel",
            background=accent_soft,
            foreground=accent,
            font=(body_family, 8, "bold"),
            padding=(9, 5),
        )
        self.style.configure(
            "State.TLabel",
            background=accent_soft,
            foreground=success,
            font=(body_family, 8, "bold"),
            padding=(9, 5),
        )
        self.style.configure(
            "AccentGlyph.TLabel",
            background=panel_alt,
            foreground=accent,
            font=(body_family, 11, "bold"),
        )
        self.style.configure(
            "Summary.TLabel",
            background=panel_alt,
            foreground=text,
            font=(body_family, 9, "bold"),
        )

        common_field = {
            "fieldbackground": field,
            "background": field,
            "foreground": text,
            "bordercolor": border,
            "lightcolor": border,
            "darkcolor": border,
            "insertcolor": text,
            "padding": (10, 8),
            "relief": "flat",
        }
        self.style.configure("TEntry", **common_field)
        self.style.configure("TSpinbox", **common_field, arrowsize=12, arrowcolor=muted)
        self.style.configure(
            "TCombobox",
            **common_field,
            arrowcolor=muted,
            selectbackground=field,
            selectforeground=text,
        )
        for widget_style in ("TEntry", "TSpinbox", "TCombobox"):
            self.style.map(
                widget_style,
                bordercolor=[("focus", accent), ("disabled", border)],
                fieldbackground=[("disabled", panel_alt), ("readonly", field)],
                foreground=[("disabled", disabled), ("readonly", text)],
                arrowcolor=[("disabled", disabled), ("readonly", muted)],
            )

        self.style.configure(
            "Primary.TButton",
            background=accent,
            foreground=accent_text,
            bordercolor=accent,
            lightcolor=accent,
            darkcolor=accent,
            relief="flat",
            padding=(18, 13),
            font=(body_family, 11, "bold"),
        )
        self.style.map(
            "Primary.TButton",
            background=[("pressed", accent_pressed), ("active", accent_hover), ("disabled", disabled)],
            bordercolor=[("pressed", accent_pressed), ("active", accent_hover)],
            lightcolor=[("pressed", accent_pressed), ("active", accent_hover)],
            darkcolor=[("pressed", accent_pressed), ("active", accent_hover)],
            foreground=[("disabled", muted)],
        )
        self.style.configure(
            "Danger.TButton",
            background=danger,
            foreground="#ffffff",
            bordercolor=danger,
            lightcolor=danger,
            darkcolor=danger,
            relief="flat",
            padding=(18, 13),
            font=(body_family, 11, "bold"),
        )
        self.style.map(
            "Danger.TButton",
            background=[("pressed", _mix_color(danger, "#000000", 0.12)), ("active", danger_hover)],
            bordercolor=[("active", danger_hover)],
            lightcolor=[("active", danger_hover)],
            darkcolor=[("active", danger_hover)],
        )
        self.style.configure(
            "Secondary.TButton",
            background=field,
            foreground=text,
            bordercolor=border,
            lightcolor=border,
            darkcolor=border,
            relief="flat",
            padding=(12, 8),
            font=(body_family, 9, "bold"),
        )
        self.style.map(
            "Secondary.TButton",
            background=[("pressed", accent_soft), ("active", panel_alt)],
            bordercolor=[("active", _mix_color(border, accent, 0.35))],
            foreground=[("disabled", disabled)],
        )
        self.style.configure(
            "Ghost.TButton",
            background=panel,
            foreground=muted,
            bordercolor=panel,
            lightcolor=panel,
            darkcolor=panel,
            relief="flat",
            padding=(11, 8),
            font=(body_family, 9, "bold"),
        )
        self.style.map(
            "Ghost.TButton",
            background=[("pressed", panel_alt), ("active", panel_alt)],
            foreground=[("active", text), ("disabled", disabled)],
            bordercolor=[("pressed", panel_alt), ("active", panel_alt)],
            lightcolor=[("pressed", panel_alt), ("active", panel_alt)],
            darkcolor=[("pressed", panel_alt), ("active", panel_alt)],
        )
        self.style.configure(
            "Link.TButton",
            background=panel,
            foreground=accent,
            bordercolor=panel,
            lightcolor=panel,
            darkcolor=panel,
            relief="flat",
            padding=(0, 4),
            font=(body_family, 9, "bold"),
        )
        self.style.map("Link.TButton", foreground=[("active", accent_hover)])
        self.style.configure(
            "Record.TButton",
            background=panel,
            foreground=danger,
            bordercolor=_mix_color(panel, danger, 0.48),
            lightcolor=_mix_color(panel, danger, 0.48),
            darkcolor=_mix_color(panel, danger, 0.48),
            relief="flat",
            padding=(12, 8),
            font=(body_family, 9, "bold"),
        )
        self.style.map(
            "Record.TButton",
            background=[("active", _mix_color(panel, danger, 0.13))],
            foreground=[("active", _mix_color(danger, "#ffffff", 0.08))],
        )

        # Radio buttons borrow the button layout, becoming a true segmented control.
        try:
            button_layout = self.style.layout("TButton")
            self.style.layout("Segment.TRadiobutton", button_layout)
            self.style.layout("WideSegment.TRadiobutton", button_layout)
        except tk.TclError:
            pass
        for segment_style, padding in (
            ("Segment.TRadiobutton", (13, 7)),
            ("WideSegment.TRadiobutton", (10, 8)),
        ):
            self.style.configure(
                segment_style,
                background=field,
                foreground=muted,
                bordercolor=field,
                lightcolor=field,
                darkcolor=field,
                relief="flat",
                padding=padding,
                anchor="center",
                font=(body_family, 9, "bold"),
            )
            self.style.map(
                segment_style,
                background=[("disabled", field), ("selected", accent_soft), ("active", panel_alt)],
                foreground=[("disabled", disabled), ("selected", accent), ("active", text)],
                bordercolor=[("selected", accent_soft)],
                lightcolor=[("selected", accent_soft)],
                darkcolor=[("selected", accent_soft)],
            )

        self.style.configure(
            "Chip.TCheckbutton",
            background=panel,
            foreground=muted,
            indicatorbackground=field,
            indicatorforeground=accent,
            bordercolor=border,
            padding=(7, 5),
            font=(body_family, 9, "bold"),
        )
        self.style.map(
            "Chip.TCheckbutton",
            foreground=[("selected", text), ("disabled", disabled)],
            indicatorbackground=[("selected", accent), ("disabled", panel_alt)],
            background=[("active", panel_alt)],
        )
        self.style.configure("TSeparator", background=border)

        self.root.option_add("*TCombobox*Listbox.background", field)
        self.root.option_add("*TCombobox*Listbox.foreground", text)
        self.root.option_add("*TCombobox*Listbox.selectBackground", accent)
        self.root.option_add("*TCombobox*Listbox.selectForeground", accent_text)
        self.root.option_add("*TCombobox*Listbox.font", (body_family, 10))

        for switch in getattr(self, "_switches", []):
            switch.set_colors(panel, accent, border, accent_text)

    def _draw_brand_mark(self):
        if not hasattr(self, "brand_canvas"):
            return
        colors = self.current_theme["colors"]
        canvas = self.brand_canvas
        canvas.configure(bg=colors["window"])
        canvas.delete("all")
        accent = colors["accent"]
        soft = _mix_color(colors["window"], accent, 0.18)
        canvas.create_oval(1, 1, 45, 45, fill=soft, outline=soft)
        canvas.create_oval(9, 9, 37, 37, outline=accent, width=3)
        canvas.create_polygon(19, 15, 19, 31, 31, 23, fill=colors["text"], outline="")

    def _update_summary(self):
        if not hasattr(self, "summary_var"):
            return

        if self.input_type_var.get() == "Keyboard":
            selected = [name for name, var in self.modifier_vars.items() if var.get()]
            action = "+".join(selected + [self.key_var.get()])
            if self.hold_mode_var.get():
                action += " held for %s ms" % (self.hold_duration_var.get() or "0")
            else:
                action += " key press"
        else:
            action = "%s %s click" % (
                self.mouse_button_var.get(),
                self.click_type_var.get().lower(),
            )

        try:
            total_ms = (
                int(self.hours_var.get() or 0) * 3600000
                + int(self.mins_var.get() or 0) * 60000
                + int(self.secs_var.get() or 0) * 1000
                + int(self.ms_var.get() or 0)
            )
            if total_ms < 1000:
                timing = "%d ms" % total_ms
            elif total_ms < 60000:
                timing = ("%.2f" % (total_ms / 1000.0)).rstrip("0").rstrip(".") + " sec"
            else:
                timing = ("%.2f" % (total_ms / 60000.0)).rstrip("0").rstrip(".") + " min"
        except ValueError:
            timing = "your interval"

        repeat = (
            "until you stop it"
            if self.repeat_mode_var.get() == "until"
            else "%s times" % (self.repeat_count_var.get() or "1")
        )
        position = (
            "at the live cursor"
            if self.cursor_mode_var.get() == "current"
            else "at (%s, %s)" % (self.x_var.get() or "0", self.y_var.get() or "0")
        )
        if self.input_type_var.get() == "Keyboard":
            position = "in the active app"
        self.summary_var.set("%s every %s, %s %s." % (action, timing, repeat, position))

    def _update_status_visual(self):
        if not hasattr(self, "status_dot"):
            return
        colors = self.current_theme["colors"]
        value = self.status_var.get().lower()
        if value.startswith("running"):
            color = colors.get("success", "#42d392")
            state = "RUNNING"
        elif "fail" in value or "emergency" in value or "error" in value:
            color = colors["danger"]
            state = "ATTENTION"
        else:
            color = colors["accent"]
            state = "READY"
        self.run_state_var.set(state)
        self.status_dot.configure(bg=colors["window"])
        self.status_dot.delete("all")
        self.status_dot.create_oval(2, 2, 10, 10, fill=color, outline=color)

    def _refresh_timing_fields(self):
        enabled_hold = self.hold_mode_var.get()
        enabled_random = self.randomize_var.get()
        self.hold_duration_spin.state(["!disabled"] if enabled_hold else ["disabled"])
        for widget in (self.random_min_spin, self.random_max_spin):
            widget.state(["!disabled"] if enabled_random else ["disabled"])

    def _refresh_repeat_fields(self):
        enabled = self.repeat_mode_var.get() == "count"
        self.repeat_count_spin.state(["!disabled"] if enabled else ["disabled"])

    def _refresh_cursor_fields(self):
        keyboard_mode = self.input_type_var.get() == "Keyboard"
        for radio in (self.cursor_live_radio, self.cursor_fixed_radio):
            radio.state(["disabled"] if keyboard_mode else ["!disabled"])
        enabled = self.cursor_mode_var.get() == "pick" and not keyboard_mode
        for widget in (self.pick_button, self.x_spin, self.y_spin):
            widget.state(["!disabled"] if enabled else ["disabled"])
        if enabled:
            self.fixed_row.grid()
        else:
            self.fixed_row.grid_remove()

    def _center_dialog(self, window, width, height):
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + max((self.root.winfo_width() - width) // 2, 0)
        y = self.root.winfo_rooty() + max((self.root.winfo_height() - height) // 2, 0)
        window.geometry("%dx%d+%d+%d" % (width, height, x, y))

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
        self.theme_var.set(c.get("theme", "Aurora"))

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
        c["theme"] = self.theme_var.get()
        return c

    # ------------------------------------------------------------- behaviors
    def _refresh_action_fields(self):
        is_keyboard = self.input_type_var.get() == "Keyboard"
        self.mouse_menu.state(["disabled"] if is_keyboard else ["!disabled", "readonly"])
        self.key_menu.state(["!disabled", "readonly"] if is_keyboard else ["disabled"])
        for box in self.modifier_boxes.values():
            box.state(["!disabled"] if is_keyboard else ["disabled"])
        if hasattr(self, "cursor_mode_var"):
            self._refresh_cursor_fields()
        self._update_summary()

    def _pick_location(self):
        import pyautogui

        x, y = pyautogui.position()
        self.x_var.set(str(int(x)))
        self.y_var.set(str(int(y)))
        self.cursor_mode_var.set("pick")
        self._refresh_cursor_fields()

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
        self._refresh_timing_fields()
        self._refresh_cursor_fields()

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
        self.status_var.set("Running · 0 actions")

    def _stop(self):
        if self.engine:
            self.engine.stop()
        if self.macro_player:
            self.macro_player.stop()

    def _update_running_ui(self, running):
        if running:
            self.start_button.config(text="Stop automation", style="Danger.TButton")
            self.run_state_var.set("RUNNING")
        else:
            self.start_button.config(style="Primary.TButton")
            self._update_hotkey_label()

    def _poll_queue(self):
        try:
            while True:
                msg, value = self.queue.get_nowait()
                if msg == "status":
                    self.status_var.set("Running · %d actions" % value)
                elif msg == "macro_status":
                    self.macro_status_var.set("Playing - actions: %d" % value)
                elif msg == "macro_done":
                    self.play_macro_button.config(text="Play", style="Secondary.TButton")
                    self.macro_status_var.set("Macro finished - actions: %d" % value)
                elif msg == "done":
                    self.status_var.set("Stopped · %d actions" % value)
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
        was_running = bool(self.engine and self.engine.running)
        macro_was_running = bool(self.macro_player and self.macro_player.running)
        self._stop()
        if was_running:
            self.status_var.set("Emergency stop")
            self._update_running_ui(False)
        if macro_was_running:
            self.macro_status_var.set("Emergency stop")
            self.play_macro_button.config(text="Play", style="Secondary.TButton")

    def _update_hotkey_label(self):
        mod = self.config["hotkey_mod"]
        key = self.config["hotkey_key"]
        if mod and mod != "None":
            label = "%s+%s" % (mod, key)
        else:
            label = key
        self.start_button.config(text="Start automation  ·  %s" % label)

    def _open_hotkey_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Quick-toggle hotkey")
        win.configure(bg=self.current_theme["colors"]["window"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        self._center_dialog(win, 500, 355)

        body = ttk.Frame(win, style="App.TFrame", padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Quick-toggle hotkey", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            body,
            text="Start or stop your automation from any app.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(3, 22))

        mod_var = tk.StringVar(value=self.config["hotkey_mod"])
        key_var = tk.StringVar(value=self.config["hotkey_key"])
        form = ttk.Frame(body, style="Card.TFrame", padding=18)
        form.grid(row=2, column=0, columnspan=2, sticky="ew")
        form.grid_columnconfigure(0, weight=1)
        form.grid_columnconfigure(1, weight=1)
        ttk.Label(form, text="MODIFIER", style="FieldLabel.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 7)
        )
        ttk.Label(form, text="KEY", style="FieldLabel.TLabel").grid(
            row=0, column=1, sticky="w", padx=(7, 0)
        )
        ttk.Combobox(
            form,
            textvariable=mod_var,
            values=HOTKEY_MODS,
            state="readonly",
        ).grid(row=1, column=0, sticky="ew", padx=(0, 7), pady=(7, 0))
        ttk.Combobox(
            form,
            textvariable=key_var,
            values=HOTKEY_KEYS,
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", padx=(7, 0), pady=(7, 0))
        ttk.Label(
            form,
            text="F12 remains the emergency stop and cannot be reassigned.",
            style="CardMuted.TLabel",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(14, 0))

        def save():
            self.config["hotkey_mod"] = mod_var.get()
            self.config["hotkey_key"] = key_var.get()
            save_config(self.config)
            self._stop_hotkey_listener()
            self._start_hotkey_listener()
            self._update_hotkey_label()
            win.destroy()

        actions = ttk.Frame(body, style="App.TFrame")
        actions.grid(row=3, column=0, columnspan=2, sticky="e", pady=(20, 0))
        ttk.Button(
            actions,
            text="Cancel",
            style="Ghost.TButton",
            command=win.destroy,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            actions,
            text="Save hotkey",
            style="Primary.TButton",
            command=save,
        ).pack(side="left")
        win.bind("<Escape>", lambda _event: win.destroy())

    # ------------------------------------------------------------------- help
    def _open_help(self):
        win = tk.Toplevel(self.root)
        win.title("AutoKeyPresser guide")
        win.configure(bg=self.current_theme["colors"]["window"])
        win.transient(self.root)
        win.resizable(True, True)
        win.minsize(580, 540)
        self._center_dialog(win, 660, 620)

        body = ttk.Frame(win, style="App.TFrame", padding=(26, 22))
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Quick start", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            body,
            text="Everything you need to build a safe, repeatable automation.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(3, 16))

        content = ttk.Frame(body, style="Card.TFrame", padding=(20, 16))
        content.pack(fill="both", expand=True)
        colors = self.current_theme["colors"]
        text = tk.Text(
            content,
            wrap="word",
            padx=4,
            pady=4,
            relief=tk.FLAT,
            bd=0,
            bg=colors["panel"],
            fg=colors["text"],
            insertbackground=colors["text"],
            selectbackground=colors["accent"],
            selectforeground=colors["accent_text"],
            font=(self.body_font, 10),
            spacing1=2,
            spacing3=8,
        )
        scroll = ttk.Scrollbar(content, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.tag_configure(
            "heading",
            foreground=colors["text"],
            font=(self.display_font, 13, "bold"),
            spacing1=12,
            spacing3=5,
        )
        text.tag_configure("body", foreground=colors["muted_text"], lmargin2=0)
        text.tag_configure(
            "callout",
            foreground=colors["text"],
            background=_mix_color(colors["panel"], colors["accent"], 0.14),
            lmargin1=12,
            lmargin2=12,
            rmargin=12,
            spacing1=10,
            spacing3=10,
        )
        sections = (
            (
                "Build an automation",
                "1. Choose Mouse or Keyboard in the Action card.\n"
                "2. Set the interval between actions.\n"
                "3. Choose a repeat rule and cursor position.\n"
                "4. Review the run-plan summary, then press Start automation.",
            ),
            (
                "Global controls",
                "The default quick-toggle is F6 and works while another app is focused. "
                "Use Change hotkey to customize it. F12 is always reserved as the emergency stop.",
            ),
            (
                "Macros and profiles",
                "Macro studio records keyboard and mouse activity into shareable .akp files. "
                "Profiles save one or more configured actions as reusable sequences.",
            ),
            (
                "Platform permissions",
                "Windows works out of the box. Linux requires an X11 session. On macOS, allow "
                "Accessibility and Input Monitoring in System Settings > Privacy & Security.",
            ),
        )
        for heading, paragraph in sections:
            text.insert(tk.END, heading + "\n", "heading")
            text.insert(tk.END, paragraph + "\n", "body")
        text.insert(
            tk.END,
            "Safety: a 0 ms interval can send input extremely quickly. Use only on content "
            "you own or are authorized to automate.",
            "callout",
        )
        text.config(state=tk.DISABLED)
        ttk.Button(
            body,
            text="Done",
            style="Primary.TButton",
            command=win.destroy,
        ).pack(anchor="e", pady=(14, 0))
        win.bind("<Escape>", lambda _event: win.destroy())

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

    # ---------------------------------------------------------------- macros
    def _load_macro_from_args(self):
        for argument in sys.argv[1:]:
            if argument.lower().endswith(".akp"):
                self._load_macro(argument)
                break

    def _load_theme_from_args(self):
        for argument in sys.argv[1:]:
            if argument.lower().endswith(".akpt"):
                try:
                    self.current_theme = themes.load_theme(argument)
                    self.theme_var.set(self.current_theme["name"])
                    self._apply_theme_data(self.current_theme)
                    return True
                except (OSError, ValueError):
                    return False
        return False

    def _toggle_record(self):
        if self.recorder and self.recorder.recording:
            self._stop_record()
            return
        self.recorder = macro.MacroRecorder()
        try:
            self.recorder.start()
        except Exception as exc:
            self.recorder = None
            messagebox.showerror(APP_NAME, "Could not start macro recording:\n%s" % exc)
            return
        self.record_button.config(text="Recording...", style="Danger.TButton")
        self.macro_status_var.set("Recording - press Stop when done")

    def _stop_record(self):
        if not self.recorder or not self.recorder.recording:
            return
        self.last_macro = self.recorder.stop()
        self.recorder = None
        self.record_button.config(text="Record", style="Record.TButton")
        self.macro_status_var.set("Recorded %d actions" % len(self.last_macro))

    def _play_macro(self):
        if self.macro_player and self.macro_player.running:
            self.macro_player.stop()
            return
        if not self.last_macro:
            messagebox.showwarning(APP_NAME, "Record or load a macro first.")
            return
        try:
            settings = self._collect_settings()
        except ValueError:
            messagebox.showerror(APP_NAME, "Please enter valid repeat values first.")
            return
        self.macro_player = macro.MacroPlayer(
            self.last_macro,
            repeat_count=settings.repeat_count,
            repeat_until_stopped=settings.repeat_until_stopped,
            on_status=self.queue.put,
        )
        self.macro_player.start()
        self.play_macro_button.config(text="Stop", style="Danger.TButton")
        self.macro_status_var.set("Playing macro...")

    def _save_macro(self):
        if not self.last_macro:
            messagebox.showwarning(APP_NAME, "Record or load a macro first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".akp",
            filetypes=[("AutoKeyPresser Macro", "*.akp")],
        )
        if not path:
            return
        try:
            macro.save_macro(self.last_macro, path)
            self.macro_status_var.set("Macro saved")
        except OSError as exc:
            messagebox.showerror(APP_NAME, "Could not save macro:\n%s" % exc)

    def _load_macro(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(
                filetypes=[("AutoKeyPresser Macro", "*.akp"), ("All files", "*.*")],
            )
        if not path:
            return
        try:
            payload = macro.load_macro(path)
        except (OSError, ValueError) as exc:
            messagebox.showerror(APP_NAME, "Could not load macro:\n%s" % exc)
            return
        self.last_macro = payload["actions"]
        self.macro_status_var.set(
            "Loaded %s (%d actions)" % (payload.get("name", "macro"), len(self.last_macro))
        )
        self.play_macro_button.config(text="Play")

    # ---------------------------------------------------------------- themes
    def _apply_theme(self, name):
        theme = self._theme_for_name(name)
        self.theme_var.set(theme["name"])
        self._apply_theme_data(theme)

    def _style_widget_tree(self, widget, colors):
        kind = widget.winfo_class()
        options = {}
        if kind in {"Tk", "Toplevel"}:
            options["bg"] = colors["window"]
        elif kind in {"Frame", "LabelFrame"}:
            options.update({"bg": colors["panel"]})
        elif kind in {"Label", "Checkbutton", "Radiobutton"}:
            options.update({"bg": colors["panel"], "fg": colors["text"]})
        elif kind in {"Entry", "Spinbox", "Listbox", "Text", "Menubutton"}:
            options.update(
                {
                    "bg": colors["input"],
                    "fg": colors["text"],
                    "insertbackground": colors["text"],
                    "selectbackground": colors["accent"],
                    "selectforeground": colors["accent_text"],
                }
            )
        if kind in {"Button", "Menubutton"}:
            options.update({
                "bg": colors["panel"],
                "fg": colors["text"],
                "activebackground": colors["accent"],
                "activeforeground": colors["accent_text"],
            })
        if kind == "LabelFrame":
            options["highlightbackground"] = colors["border"]
        try:
            widget.configure(**options)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._style_widget_tree(child, colors)

    def _apply_selected_theme(self):
        self._apply_theme(self.theme_var.get())
        self.config["theme"] = self.theme_var.get()
        save_config(self.config)
        self.status_var.set("Appearance updated")

    def _open_theme_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Appearance")
        win.configure(bg=self.current_theme["colors"]["window"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        self._center_dialog(win, 570, 455)

        body = ttk.Frame(win, style="App.TFrame", padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Appearance", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            body,
            text="Choose a mood or bring your own signed .akpt theme.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 20))

        card = ttk.Frame(body, style="Card.TFrame", padding=18)
        card.grid(row=2, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        ttk.Label(card, text="THEME", style="FieldLabel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        choices = list(themes.theme_names())
        if self.theme_var.get() not in choices:
            choices.append(self.theme_var.get())
        self.theme_picker = ttk.Combobox(
            card,
            textvariable=self.theme_var,
            values=choices,
            state="readonly",
        )
        self.theme_picker.grid(row=1, column=0, sticky="ew", pady=(7, 16))

        palette = tk.Canvas(
            card,
            height=76,
            highlightthickness=0,
            bd=0,
        )
        palette.grid(row=2, column=0, sticky="ew")

        def draw_palette(_event=None):
            colors = self.current_theme["colors"]
            palette.configure(bg=colors["panel"])
            palette.delete("all")
            palette.update_idletasks()
            width = max(palette.winfo_width(), 470)
            swatches = (
                colors["window"],
                colors["panel"],
                colors["input"],
                colors["accent"],
                colors.get("success", "#42d392"),
                colors["danger"],
            )
            gap = 8
            swatch_width = (width - gap * (len(swatches) - 1)) / len(swatches)
            for index, color in enumerate(swatches):
                x0 = index * (swatch_width + gap)
                palette.create_rectangle(
                    x0,
                    8,
                    x0 + swatch_width,
                    64,
                    fill=color,
                    outline=colors["border"],
                    width=1,
                )

        def choose_theme(_event=None):
            self._apply_selected_theme()
            draw_palette()

        self.theme_picker.bind("<<ComboboxSelected>>", choose_theme)
        palette.bind("<Configure>", draw_palette)
        draw_palette()

        ttk.Label(
            body,
            text="Themes update live and are remembered for the next launch.",
            style="Muted.TLabel",
        ).grid(row=3, column=0, sticky="w", pady=(14, 18))

        actions = ttk.Frame(body, style="App.TFrame")
        actions.grid(row=4, column=0, sticky="ew")
        ttk.Button(
            actions,
            text="Import theme",
            style="Ghost.TButton",
            command=lambda: (self._import_theme(), draw_palette()),
        ).pack(side="left")
        ttk.Button(
            actions,
            text="Export current",
            style="Ghost.TButton",
            command=self._export_theme,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            actions,
            text="Done",
            style="Primary.TButton",
            command=win.destroy,
        ).pack(side="right")
        win.bind("<Escape>", lambda _event: win.destroy())

    def _import_theme(self):
        path = filedialog.askopenfilename(
            filetypes=[("AutoKeyPresser Theme", "*.akpt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            theme = themes.load_theme(path)
            saved = themes.save_user_theme(theme)
        except (OSError, ValueError) as exc:
            messagebox.showerror(APP_NAME, "Could not import theme:\n%s" % exc)
            return
        self.current_theme = theme
        self.theme_var.set(theme["name"])
        self._apply_theme_data(theme)
        if hasattr(self, "theme_picker") and self.theme_picker.winfo_exists():
            values = list(self.theme_picker.cget("values"))
            if theme["name"] not in values:
                self.theme_picker.configure(values=values + [theme["name"]])
        self.config["theme"] = theme["name"]
        save_config(self.config)
        self.status_var.set("Theme imported: %s" % saved.name)

    def _export_theme(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".akpt",
            filetypes=[("AutoKeyPresser Theme", "*.akpt")],
        )
        if path:
            try:
                themes.save_theme(self.current_theme, path)
                self.status_var.set("Theme exported")
            except OSError as exc:
                messagebox.showerror(APP_NAME, "Could not export theme:\n%s" % exc)

    def _apply_theme_data(self, theme):
        self.current_theme = themes.validate_theme(theme)
        colors = self.current_theme["colors"]
        self.root.configure(bg=colors["window"])
        self._configure_styles(colors)
        self._style_widget_tree(self.root, colors)
        self._draw_brand_mark()
        self._update_status_visual()

    def _open_profiles(self):
        profiles = load_profiles()
        win = tk.Toplevel(self.root)
        win.title("Profiles and sequences")
        win.configure(bg=self.current_theme["colors"]["window"])
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        self._center_dialog(win, 760, 500)

        body = ttk.Frame(win, style="App.TFrame", padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Profiles", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            body,
            text="Save this setup once, then launch it in a click.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(3, 20))
        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=3)
        body.grid_rowconfigure(2, weight=1)

        colors = self.current_theme["colors"]
        library = ttk.Frame(body, style="Card.TFrame", padding=14)
        library.grid(row=2, column=0, sticky="nsew", padx=(0, 9))
        library.grid_columnconfigure(0, weight=1)
        library.grid_rowconfigure(1, weight=1)
        ttk.Label(library, text="SAVED PROFILES", style="FieldLabel.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )
        names = tk.StringVar(value=tuple(sorted(profiles)))
        listing = tk.Listbox(
            library,
            listvariable=names,
            exportselection=False,
            activestyle="none",
            relief=tk.FLAT,
            bd=0,
            highlightthickness=1,
            highlightbackground=colors["border"],
            highlightcolor=colors["accent"],
            bg=colors["input"],
            fg=colors["text"],
            selectbackground=colors["accent"],
            selectforeground=colors["accent_text"],
            font=(self.body_font, 10),
        )
        listing.grid(row=1, column=0, sticky="nsew")

        editor = ttk.Frame(body, style="Card.TFrame", padding=18)
        editor.grid(row=2, column=1, sticky="nsew", padx=(9, 0))
        editor.grid_columnconfigure(0, weight=1)
        ttk.Label(editor, text="PROFILE DETAILS", style="FieldLabel.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(editor, text="Name", style="CardLabel.TLabel").grid(
            row=1, column=0, sticky="w", pady=(16, 6)
        )
        name_var = tk.StringVar()
        ttk.Entry(editor, textvariable=name_var).grid(row=2, column=0, sticky="ew")
        detail_var = tk.StringVar(value="Create a profile from the current action.")
        detail = ttk.Frame(editor, style="Inset.TFrame", padding=(14, 12))
        detail.grid(row=3, column=0, sticky="ew", pady=(18, 0))
        ttk.Label(
            detail,
            textvariable=detail_var,
            style="Summary.TLabel",
            wraplength=330,
            justify="left",
        ).pack(anchor="w")

        def selected_name():
            selected = listing.curselection()
            return listing.get(selected[0]) if selected else name_var.get().strip()

        def describe(_event=None):
            selected = listing.curselection()
            if not selected:
                return
            name = listing.get(selected[0])
            name_var.set(name)
            count = len(profiles.get(name, {}).get("actions", []))
            detail_var.set(
                "%s contains %d action%s. Load it to edit, or run the full sequence now."
                % (name, count, "" if count == 1 else "s")
            )

        listing.bind("<<ListboxSelect>>", describe)

        def refresh(select_name=None):
            ordered = sorted(profiles)
            names.set(tuple(ordered))
            if select_name in ordered:
                index = ordered.index(select_name)
                listing.selection_clear(0, tk.END)
                listing.selection_set(index)
                listing.see(index)
                describe()
            elif not ordered:
                detail_var.set("No saved profiles yet. Name the current setup to create one.")

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
            refresh(name)
            self.status_var.set("Profile saved: %s" % name)

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
            refresh(name)
            self.status_var.set("Action added to %s" % name)

        def load_profile(run=False):
            name = selected_name()
            profile = profiles.get(name, {})
            actions = profile.get("actions", [])
            if not actions:
                return
            self._apply_action(actions[0])
            self.pending_actions = actions if len(actions) > 1 else []
            self.status_var.set("Profile loaded: %s" % name)
            if run:
                win.destroy()
                self._start()

        def delete_profile():
            name = selected_name()
            if name in profiles and messagebox.askyesno(
                APP_NAME,
                "Delete the profile '%s'?" % name,
                parent=win,
            ):
                del profiles[name]
                save_profiles(profiles)
                refresh()
                name_var.set("")
                self.status_var.set("Profile deleted")

        primary_actions = ttk.Frame(editor, style="Panel.TFrame")
        primary_actions.grid(row=4, column=0, sticky="ew", pady=(20, 0))
        ttk.Button(
            primary_actions,
            text="Save current",
            style="Secondary.TButton",
            command=save_current,
        ).pack(side="left")
        ttk.Button(
            primary_actions,
            text="Add action",
            style="Ghost.TButton",
            command=add_action,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            primary_actions,
            text="Delete",
            style="Record.TButton",
            command=delete_profile,
        ).pack(side="right")

        footer = ttk.Frame(body, style="App.TFrame")
        footer.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(18, 0))
        ttk.Button(
            footer,
            text="Close",
            style="Ghost.TButton",
            command=win.destroy,
        ).pack(side="left")
        ttk.Button(
            footer,
            text="Load profile",
            style="Secondary.TButton",
            command=load_profile,
        ).pack(side="right", padx=(8, 0))
        ttk.Button(
            footer,
            text="Run sequence",
            style="Primary.TButton",
            command=lambda: load_profile(True),
        ).pack(side="right")
        refresh()
        win.bind("<Escape>", lambda _event: win.destroy())
