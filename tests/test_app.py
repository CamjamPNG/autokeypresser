import json
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

from autoclicker import config as config_module
from autoclicker import keys
from autoclicker import profiles as profiles_module
from autoclicker import updater
from autoclicker.app import (
    APP_NAME,
    InvalidSettings,
    build_hotkey,
    checked_text,
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


class VersionTests(unittest.TestCase):
    def test_app_reports_the_version_the_updater_checks(self):
        self.assertEqual(updater.CURRENT_VERSION, "2.0.1")
        self.assertEqual(APP_NAME, "AutoKeyPresser 2.0.1")


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
