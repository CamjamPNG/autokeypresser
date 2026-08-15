import unittest

from autoclicker import keys
from autoclicker.app import build_hotkey
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


if __name__ == "__main__":
    unittest.main()
