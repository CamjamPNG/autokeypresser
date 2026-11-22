import json
import pathlib
import shutil
import tempfile
import tkinter as tk
import unittest
from unittest import mock

from autoclicker import app as app_module
from autoclicker import config as config_module
from autoclicker import keys
from autoclicker import profiles as profiles_module
from autoclicker import updater
from autoclicker.app import (
    APP_NAME,
    InvalidSettings,
    build_hotkey,
    checked_delay,
    checked_text,
    describe_step,
    input_type_for,
    mode_for,
    settings_to_action,
)
from autoclicker.engine import PressSettings


class KeyMappingTests(unittest.TestCase):
    def test_letters_and_digits(self):
        self.assertEqual(keys.display_to_key("A"), "a")
        self.assertEqual(keys.display_to_key("5"), "5")

    def test_function_keys(self):
        self.assertEqual(keys.display_to_key("F12"), "f12")

    def test_special_keys(self):
        self.assertEqual(keys.display_to_key("Space"), "space")
        self.assertEqual(keys.display_to_key("Page Up"), "pageup")
        self.assertEqual(keys.display_to_key("Print Screen"), "printscreen")

    def test_unknown_falls_back(self):
        self.assertEqual(keys.display_to_key("Nope"), "nope")

    def test_modifier_os_names(self):
        self.assertEqual(keys.os_modifier("Ctrl"), "ctrl")
        self.assertIn(keys.os_modifier("Win/Cmd"), ("win", "command"))


class HotkeyBuilderTests(unittest.TestCase):
    def test_plain_f_key(self):
        self.assertEqual(build_hotkey("None", "F6"), "<f6>")

    def test_two_digit_f_key(self):
        self.assertEqual(build_hotkey("None", "F12"), "<f12>")

    def test_special_key(self):
        self.assertEqual(build_hotkey("None", "Page Up"), "<page_up>")

    def test_letter(self):
        self.assertEqual(build_hotkey("None", "H"), "h")

    def test_with_modifier(self):
        self.assertEqual(build_hotkey("Ctrl", "F6"), "<ctrl>+<f6>")

    def test_with_multiple_modifiers(self):
        self.assertEqual(build_hotkey("Ctrl+Alt", "H"), "<ctrl>+<alt>+h")


class SettingsTests(unittest.TestCase):
    def test_defaults(self):
        s = PressSettings()
        self.assertTrue(s.repeat_until_stopped)
        self.assertEqual(s.mouse_button, "left")
        self.assertEqual(s.interval_seconds, 0.1)


class TextValidationTests(unittest.TestCase):
    def test_rejects_empty_string(self):
        with self.assertRaises(InvalidSettings):
            checked_text("")

    def test_rejects_whitespace_only(self):
        with self.assertRaises(InvalidSettings):
            checked_text("   ")

    def test_rejects_control_characters(self):
        for raw in ("two\nlines", "tab\there", "bell\a"):
            with self.assertRaises(InvalidSettings):
                checked_text(raw)

    def test_rejects_non_ascii(self):
        for raw in ("caf\u00e9", "smart \u201cquotes\u201d", "\U0001f600"):
            with self.assertRaises(InvalidSettings):
                checked_text(raw)

    def test_keeps_punctuation_and_spacing(self):
        raw = "  Hello, world! 100% + (yes) = done?  "
        self.assertEqual(checked_text(raw), raw)


class TextActionTests(unittest.TestCase):
    def test_mode_labels_map_to_input_types(self):
        self.assertEqual(input_type_for("Text"), "text")
        self.assertEqual(mode_for("text"), "Text")
        self.assertEqual(mode_for("keyboard"), "Keyboard")
        self.assertEqual(mode_for("mouse"), "Mouse")

    def test_unknown_input_type_falls_back_to_mouse(self):
        self.assertEqual(mode_for("touch"), "Mouse")
        self.assertEqual(input_type_for("Pen"), "mouse")

    def test_settings_to_action_keeps_text(self):
        action = settings_to_action(PressSettings(input_type="text", text="npm run build"))
        self.assertEqual(action["input_type"], "text")
        self.assertEqual(action["text"], "npm run build")

    def test_settings_to_action_keeps_legacy_fields(self):
        action = settings_to_action(
            PressSettings(input_type="keyboard", key="c", modifiers=["ctrl"], click_type="double")
        )
        self.assertEqual(action["input_type"], "keyboard")
        self.assertEqual(action["key"], "c")
        self.assertEqual(action["modifiers"], ["ctrl"])
        self.assertEqual(action["click_type"], "double")
        self.assertEqual(action["text"], "")


class ProfileStepHelperTests(unittest.TestCase):
    """The step list keeps its order in pure list arithmetic, with no Tk involved."""

    def steps(self):
        return [{"input_type": "keyboard", "key": key} for key in ("a", "b", "c")]

    def keys(self, steps):
        return [step["key"] for step in steps]

    def test_move_swaps_neighbours_and_leaves_the_input_alone(self):
        steps = self.steps()

        self.assertEqual(self.keys(profiles_module.move_step(steps, 1, -1)), ["b", "a", "c"])
        self.assertEqual(self.keys(profiles_module.move_step(steps, 1, 1)), ["a", "c", "b"])
        self.assertEqual(self.keys(steps), ["a", "b", "c"])

    def test_moving_beyond_either_end_does_nothing(self):
        steps = self.steps()

        for index, offset in ((0, -1), (2, 1), (3, -1), (-1, 1)):
            self.assertEqual(profiles_module.move_step(steps, index, offset), steps)

    def test_remove_drops_only_the_named_step(self):
        steps = self.steps()

        self.assertEqual(self.keys(profiles_module.remove_step(steps, 1)), ["a", "c"])
        self.assertEqual(self.keys(profiles_module.remove_step(steps, 9)), ["a", "b", "c"])
        self.assertEqual(self.keys(steps), ["a", "b", "c"])

    def test_removing_the_only_step_leaves_an_empty_list(self):
        self.assertEqual(profiles_module.remove_step(self.steps()[:1], 0), [])

    def test_replace_swaps_in_the_new_step_and_keeps_the_rest(self):
        new = {"input_type": "text", "text": "hello"}

        replaced = profiles_module.replace_step(self.steps(), 2, new)

        self.assertEqual(replaced[2], new)
        self.assertEqual(self.keys(replaced[:2]), ["a", "b"])
        self.assertEqual(self.keys(profiles_module.replace_step(self.steps(), 5, new)), ["a", "b", "c"])

    def test_with_steps_keeps_the_other_profile_fields(self):
        profiles = {"Sequence": {"actions": [{"input_type": "keyboard", "key": "a"}], "note": "keep"}}

        updated = profiles_module.with_steps(
            profiles, "Sequence", [{"input_type": "keyboard", "key": "b"}]
        )

        self.assertEqual(updated["Sequence"]["note"], "keep")
        self.assertEqual(self.keys(updated["Sequence"]["actions"]), ["b"])
        self.assertEqual(self.keys(profiles["Sequence"]["actions"]), ["a"])


class ProfileStepPersistenceTests(unittest.TestCase):
    """What the step editor writes to disk, checked against the file itself."""

    def setUp(self):
        self.directory = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        patcher = mock.patch.multiple(
            profiles_module,
            PROFILE_DIR=self.directory,
            PROFILE_FILE=self.directory / "profiles.json",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def action(self, key):
        return settings_to_action(PressSettings(input_type="keyboard", key=key))

    def seed(self):
        profiles_module.save_profiles(
            {"Sequence": {"actions": [self.action("a"), self.action("b"), self.action("c")]}}
        )

    def stored_keys(self):
        return [step["key"] for step in profiles_module.load_profiles()["Sequence"]["actions"]]

    def test_the_helpers_keep_step_order_through_a_save(self):
        self.seed()

        steps = profiles_module.load_profiles()["Sequence"]["actions"]
        reordered = profiles_module.move_step(profiles_module.move_step(steps, 2, -1), 0, 1)
        profiles_module.save_profiles(
            profiles_module.with_steps(profiles_module.load_profiles(), "Sequence", reordered)
        )

        self.assertEqual(self.stored_keys(), ["c", "a", "b"])

    def test_a_removed_step_is_gone_from_disk_after_save(self):
        self.seed()

        steps = profiles_module.remove_step(
            profiles_module.load_profiles()["Sequence"]["actions"], 1
        )
        profiles_module.save_profiles(
            profiles_module.with_steps(profiles_module.load_profiles(), "Sequence", steps)
        )

        self.assertEqual(self.stored_keys(), ["a", "c"])

    def test_replacing_a_step_persists_the_new_action(self):
        self.seed()
        replacement = settings_to_action(PressSettings(input_type="text", text="hello"))

        steps = profiles_module.replace_step(
            profiles_module.load_profiles()["Sequence"]["actions"], 0, replacement
        )
        profiles_module.save_profiles(
            profiles_module.with_steps(profiles_module.load_profiles(), "Sequence", steps)
        )

        stored = profiles_module.load_profiles()["Sequence"]["actions"]
        self.assertEqual(stored[0], replacement)
        self.assertEqual(stored[1]["key"], "b")
        self.assertEqual(list(stored[0]), list(self.action("a")))


class StepLabelTests(unittest.TestCase):
    def test_keyboard_step_names_modifiers_and_key(self):
        action = settings_to_action(
            PressSettings(input_type="keyboard", key="c", modifiers=["ctrl", "shift"])
        )

        self.assertEqual(describe_step(0, action), "1. Key Ctrl + Shift + C")

    def test_mouse_step_names_the_button_and_the_place(self):
        action = settings_to_action(
            PressSettings(
                input_type="mouse",
                mouse_button="left",
                use_fixed_position=True,
                fixed_x=12,
                fixed_y=34,
            )
        )

        self.assertEqual(describe_step(2, action), "3. Mouse Left single click, at (12, 34)")

    def test_text_step_shortens_a_long_string(self):
        action = settings_to_action(PressSettings(input_type="text", text="x" * 50))

        label = describe_step(0, action)

        self.assertTrue(label.startswith("1. Type xxx"))
        self.assertTrue(label.endswith("..."))


class ProfileTextRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.directory = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        patcher = mock.patch.multiple(
            profiles_module,
            PROFILE_DIR=self.directory,
            PROFILE_FILE=self.directory / "profiles.json",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_text_action_round_trips_through_a_profile(self):
        action = settings_to_action(
            PressSettings(input_type="text", text="Type this sentence: once.")
        )
        profiles_module.save_profiles({"Greeting": {"actions": [action]}})

        restored = profiles_module.load_profiles()["Greeting"]["actions"][0]

        self.assertEqual(restored, action)
        self.assertEqual(restored["input_type"], "text")
        self.assertEqual(restored["text"], "Type this sentence: once.")

    def test_action_saved_before_text_mode_still_loads(self):
        legacy = {
            "input_type": "keyboard",
            "mouse_button": "left",
            "key": "a",
            "modifiers": [],
            "click_type": "single",
            "use_fixed_position": False,
            "fixed_x": 0,
            "fixed_y": 0,
            "hold_mode": False,
            "hold_duration_seconds": 0.05,
            "randomize_interval": False,
            "random_min_seconds": 0.05,
            "random_max_seconds": 0.15,
        }
        profiles_module.save_profiles({"Old": {"actions": [legacy]}})

        restored = profiles_module.load_profiles()["Old"]["actions"][0]

        self.assertEqual(restored, legacy)
        self.assertEqual(restored.get("text", ""), "")


class ConfigTextTests(unittest.TestCase):
    def setUp(self):
        self.directory = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        patcher = mock.patch.multiple(
            config_module,
            CONFIG_DIR=self.directory,
            CONFIG_FILE=self.directory / "config.json",
            LEGACY_CONFIG_FILE=self.directory / "legacy.json",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_saved_text_restores_on_the_next_launch(self):
        saved = config_module.load_config()
        saved.update({"input_type": "text", "text": "echo hello world"})
        config_module.save_config(saved)

        restored = config_module.load_config()

        self.assertEqual(restored["input_type"], "text")
        self.assertEqual(restored["text"], "echo hello world")

    def test_config_saved_before_text_mode_still_loads(self):
        legacy = {"input_type": "keyboard", "key": "b", "ms": "250"}
        (self.directory / "config.json").write_text(json.dumps(legacy), encoding="utf-8")

        restored = config_module.load_config()

        self.assertEqual(restored["key"], "b")
        self.assertEqual(restored["ms"], "250")
        self.assertEqual(restored["text"], "")

    def test_defaults_carry_an_empty_text_field(self):
        self.assertEqual(config_module.DEFAULTS["text"], "")


class DelayValidationTests(unittest.TestCase):
    def test_accepts_the_whole_range(self):
        self.assertEqual(checked_delay("0"), 0)
        self.assertEqual(checked_delay(" 7 "), 7)
        self.assertEqual(checked_delay("30"), 30)

    def test_range_has_its_own_message(self):
        for raw in ("-1", "31", "600"):
            with self.assertRaises(InvalidSettings) as raised:
                checked_delay(raw)
            self.assertEqual(
                str(raised.exception),
                "Start delay must be between 0 and 30 seconds.",
            )

    def test_non_numeric_has_its_own_message(self):
        for raw in ("", "soon", "2.5"):
            with self.assertRaises(InvalidSettings) as raised:
                checked_delay(raw)
            self.assertEqual(
                str(raised.exception),
                "Start delay must be a whole number from 0 to 30.",
            )


class ConfigStartDelayTests(unittest.TestCase):
    def setUp(self):
        self.directory = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        patcher = mock.patch.multiple(
            config_module,
            CONFIG_DIR=self.directory,
            CONFIG_FILE=self.directory / "config.json",
            LEGACY_CONFIG_FILE=self.directory / "legacy.json",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_saved_delay_restores_on_the_next_launch(self):
        saved = config_module.load_config()
        saved["start_delay_s"] = "5"
        config_module.save_config(saved)

        self.assertEqual(config_module.load_config()["start_delay_s"], "5")

    def test_defaults_start_with_no_delay(self):
        self.assertEqual(config_module.DEFAULTS["start_delay_s"], "0")

    def test_config_saved_before_the_delay_key_still_loads(self):
        (self.directory / "config.json").write_text(
            json.dumps({"input_type": "mouse", "ms": "250"}), encoding="utf-8"
        )

        restored = config_module.load_config()

        self.assertEqual(restored["ms"], "250")
        self.assertEqual(restored["start_delay_s"], "0")


class StartDelayAppTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: %s" % exc)
        self.addCleanup(self.root.destroy)
        with mock.patch.object(app_module.AutoClickerApp, "_start_hotkey_listener"), \
             mock.patch.object(app_module.AutoClickerApp, "_check_for_updates"):
            self.app = app_module.AutoClickerApp(self.root)

    def test_delay_reaches_the_engine_on_start(self):
        self.app.start_delay_var.set("5")

        with mock.patch.object(app_module, "PressEngine") as engine_class:
            self.app._start()

        self.assertEqual(self.app.settings.start_delay_seconds, 5.0)
        self.assertEqual(
            engine_class.call_args.args[0].start_delay_seconds, 5.0
        )

    def test_out_of_range_delay_is_reported_by_its_own_message(self):
        self.app.start_delay_var.set("45")

        with mock.patch.object(app_module, "messagebox") as box, \
             mock.patch.object(app_module, "PressEngine") as engine_class:
            self.app._start()

        self.assertEqual(
            box.showerror.call_args.args[1],
            "Start delay must be between 0 and 30 seconds.",
        )
        engine_class.assert_not_called()

    def test_non_numeric_delay_is_reported_by_its_own_message(self):
        self.app.start_delay_var.set("soon")

        with mock.patch.object(app_module, "messagebox") as box, \
             mock.patch.object(app_module, "PressEngine") as engine_class:
            self.app._start()

        self.assertEqual(
            box.showerror.call_args.args[1],
            "Start delay must be a whole number from 0 to 30.",
        )
        engine_class.assert_not_called()

    def test_macro_playback_ignores_an_invalid_delay(self):
        self.app.input_type_var.set("Text")
        self.app.text_var.set("")
        self.app.start_delay_var.set("45")
        self.app.last_macro = [{"kind": "key", "key": "a", "action": "press", "at": 0.0}]

        with mock.patch.object(app_module, "messagebox") as box, \
             mock.patch.object(app_module.macro, "MacroPlayer") as player:
            self.app._play_macro()

        box.showerror.assert_not_called()
        player.assert_called_once()

    def test_summary_names_the_delay_before_the_repeat_rule(self):
        self.app.start_delay_var.set("5")
        self.assertIn("after a 5 s delay, until you stop it", self.app.summary_var.get())

        self.app.start_delay_var.set("0")
        self.assertNotIn("delay", self.app.summary_var.get())

    def test_countdown_shows_in_the_run_plan_and_clears_on_done(self):
        self.app.start_delay_var.set("5")
        with mock.patch.object(app_module, "PressEngine"):
            self.app._start()
        self.assertEqual(
            self.app.countdown_var.get(), "5 s left · Stop or F12 cancels"
        )
        self.assertEqual(self.app.status_var.get(), "Starting in 5 s")

        self.app.queue.put(("countdown", 3))
        self.app._poll_queue()
        self.assertEqual(
            self.app.countdown_var.get(), "3 s left · Stop or F12 cancels"
        )
        self.assertEqual(self.app.status_var.get(), "Starting in 3 s")

        # The first action ends the pre-roll, so the countdown line goes away.
        self.app.queue.put(("status", 1))
        self.app._poll_queue()
        self.assertEqual(self.app.countdown_var.get(), "")

        self.app.queue.put(("done", 1))
        self.app._poll_queue()
        self.assertEqual(self.app.countdown_var.get(), "")
        self.assertEqual(self.app.status_var.get(), "Stopped · 1 actions")


class MacroPlaybackTests(unittest.TestCase):
    """Playback needs only the repeat rules, and names a range that cannot work."""

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: %s" % exc)
        self.addCleanup(self.root.destroy)
        with mock.patch.object(app_module.AutoClickerApp, "_start_hotkey_listener"), \
             mock.patch.object(app_module.AutoClickerApp, "_check_for_updates"):
            self.app = app_module.AutoClickerApp(self.root)
        self.app.last_macro = [{"kind": "key", "key": "a", "action": "press", "at": 0.0}]

    def test_random_range_conflict_blocks_playback_with_its_own_message(self):
        self.app.input_type_var.set("Text")
        self.app.randomize_var.set(True)
        self.app.random_min_var.set("300")
        self.app.random_max_var.set("100")

        with mock.patch.object(app_module, "messagebox") as box, \
             mock.patch.object(app_module.macro, "MacroPlayer") as player:
            self.app._play_macro()

        self.assertEqual(
            box.showerror.call_args.args[1],
            "Random maximum must not be lower than minimum.",
        )
        player.assert_not_called()

    def test_playback_ignores_an_unfinished_text_entry(self):
        self.app.input_type_var.set("Text")
        self.app.text_var.set("")

        with mock.patch.object(app_module, "messagebox") as box, \
             mock.patch.object(app_module.macro, "MacroPlayer") as player:
            self.app._play_macro()

        box.showerror.assert_not_called()
        player.assert_called_once()


class ProfileStepDialogTests(unittest.TestCase):
    """The dialog itself: selection, reordering, and what Save does to the file."""

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest("Tk display unavailable: %s" % exc)
        self.addCleanup(self.root.destroy)
        self.directory = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        patcher = mock.patch.multiple(
            profiles_module,
            PROFILE_DIR=self.directory,
            PROFILE_FILE=self.directory / "profiles.json",
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        profiles_module.save_profiles(
            {
                "Sequence": {
                    "actions": [self.step("a"), self.step("b"), self.step("c")]
                },
                "Solo": {"actions": [self.step("d")]},
            }
        )
        with mock.patch.object(app_module.AutoClickerApp, "_start_hotkey_listener"), \
             mock.patch.object(app_module.AutoClickerApp, "_check_for_updates"):
            self.app = app_module.AutoClickerApp(self.root)
        self.dialog = app_module.ProfileDialog(self.app)
        self.addCleanup(self._close_dialog)

    def _close_dialog(self):
        try:
            self.dialog.win.destroy()
        except tk.TclError:
            pass

    def step(self, key):
        return settings_to_action(PressSettings(input_type="keyboard", key=key))

    def dialog_keys(self):
        return [step["key"] for step in self.dialog.steps]

    def stored_keys(self, name="Sequence"):
        return [step["key"] for step in profiles_module.load_profiles()[name]["actions"]]

    def test_the_list_shows_every_step_in_order(self):
        self.dialog.select_profile("Sequence")

        shown = [
            self.dialog.step_list.get(index)
            for index in range(self.dialog.step_list.size())
        ]

        self.assertEqual(
            shown, ["1. Key A", "2. Key B", "3. Key C"]
        )

    def test_move_down_then_save_writes_the_new_order(self):
        self.dialog.select_profile("Sequence")
        self.dialog.select_step(0)

        self.dialog.move_down()

        self.assertEqual(self.dialog_keys(), ["b", "a", "c"])
        self.assertTrue(self.dialog.unsaved_changes())
        self.assertEqual(self.stored_keys(), ["a", "b", "c"])

        self.dialog.save_steps()

        self.assertFalse(self.dialog.unsaved_changes())
        self.assertEqual(self.stored_keys(), ["b", "a", "c"])

    def test_move_up_on_the_first_step_does_nothing(self):
        self.dialog.select_profile("Sequence")
        self.dialog.select_step(0)

        self.dialog.move_up()

        self.assertEqual(self.dialog_keys(), ["a", "b", "c"])
        self.assertFalse(self.dialog.unsaved_changes())
        self.assertIn("already first", self.dialog.preview_var.get())

    def test_move_down_on_the_last_step_does_nothing(self):
        self.dialog.select_profile("Sequence")
        self.dialog.select_step(2)

        self.dialog.move_down()

        self.assertEqual(self.dialog_keys(), ["a", "b", "c"])
        self.assertIn("already last", self.dialog.preview_var.get())

    def test_remove_then_save_drops_the_step_from_disk(self):
        self.dialog.select_profile("Sequence")
        self.dialog.select_step(1)

        self.dialog.remove_step()

        self.assertEqual(self.dialog_keys(), ["a", "c"])
        self.assertEqual(self.stored_keys(), ["a", "b", "c"])

        self.dialog.save_steps()

        self.assertEqual(self.stored_keys(), ["a", "c"])

    def test_removing_the_only_step_leaves_an_empty_profile(self):
        self.dialog.select_profile("Solo")
        self.dialog.select_step(0)

        self.dialog.remove_step()

        self.assertEqual(self.dialog.steps, [])
        self.assertEqual(self.dialog.step_list.get(0), "No steps yet - use Add action.")

        self.dialog.save_steps()

        self.assertEqual(self.stored_keys("Solo"), [])

    def test_replace_with_the_current_action_persists_it(self):
        self.dialog.select_profile("Sequence")
        self.dialog.select_step(1)
        self.app.input_type_var.set("Keyboard")
        self.app.key_var.set("Enter")
        self.app.modifier_vars["Ctrl"].set(True)

        self.dialog.replace_step()
        self.dialog.save_steps()

        stored = profiles_module.load_profiles()["Sequence"]["actions"]
        self.assertEqual(stored[1]["key"], "enter")
        self.assertEqual(stored[1]["modifiers"], ["ctrl"])
        self.assertEqual([step["key"] for step in stored], ["a", "enter", "c"])

    def test_replace_with_no_step_selected_says_so(self):
        self.dialog.select_profile("Sequence")

        with mock.patch.object(app_module, "messagebox") as box:
            self.dialog.replace_step()

        self.assertEqual(box.showwarning.call_args.args[1], "Select the step to replace first.")
        self.assertEqual(self.dialog_keys(), ["a", "b", "c"])
        box.showerror.assert_not_called()

    def test_an_invalid_current_action_keeps_its_own_message(self):
        self.dialog.select_profile("Sequence")
        self.dialog.select_step(0)
        self.app.input_type_var.set("Text")
        self.app.text_var.set("")

        with mock.patch.object(app_module, "messagebox") as box:
            self.dialog.replace_step()

        self.assertEqual(
            box.showerror.call_args.args[1], "Enter the text to type first."
        )
        self.assertEqual(self.dialog_keys(), ["a", "b", "c"])
        self.assertFalse(self.dialog.unsaved_changes())

    def test_closing_with_unsaved_edits_asks_and_writes_nothing(self):
        self.dialog.select_profile("Sequence")
        self.dialog.select_step(2)
        self.dialog.remove_step()

        with mock.patch.object(app_module, "messagebox") as box:
            box.askyesno.return_value = True
            self.dialog.close()

        self.assertEqual(self.stored_keys(), ["a", "b", "c"])

    def test_cancelling_the_close_discard_keeps_the_edits(self):
        self.dialog.select_profile("Sequence")
        self.dialog.select_step(2)
        self.dialog.remove_step()

        with mock.patch.object(app_module, "messagebox") as box:
            box.askyesno.return_value = False
            self.dialog.close()

        self.assertTrue(self.dialog.unsaved_changes())
        self.assertEqual(self.dialog_keys(), ["a", "b"])
        self.assertEqual(self.stored_keys(), ["a", "b", "c"])

    def test_saving_keeps_the_profile_json_shape(self):
        self.dialog.select_profile("Sequence")
        self.dialog.select_step(0)
        self.dialog.move_down()
        self.dialog.save_steps()

        raw = json.loads((self.directory / "profiles.json").read_text(encoding="utf-8"))

        self.assertEqual(sorted(raw), ["Sequence", "Solo"])
        self.assertEqual(list(raw["Sequence"]), ["actions"])
        self.assertEqual(list(raw["Sequence"]["actions"][0]), list(self.step("a")))


class VersionTests(unittest.TestCase):
    def test_app_reports_the_version_the_updater_checks(self):
        self.assertEqual(updater.CURRENT_VERSION, "2.0.3")
        self.assertEqual(APP_NAME, "AutoKeyPresser 2.0.3")


class UpdaterTests(unittest.TestCase):
    def test_version_comparison(self):
        self.assertTrue(updater.is_newer("v2.1"))
        self.assertFalse(updater.is_newer("v2.0"))
        self.assertFalse(updater.is_newer("v1.9"))
        self.assertFalse(updater.is_newer("not-a-version"))

    def test_windows_installer_asset(self):
        release = {"assets": [{"name": "AutoKeyPresser-Setup.exe", "browser_download_url": "url"}]}
        with mock.patch.object(updater.platform, "system", return_value="Windows"):
            self.assertEqual(updater.installer_asset(release), "url")


if __name__ == "__main__":
    unittest.main()
