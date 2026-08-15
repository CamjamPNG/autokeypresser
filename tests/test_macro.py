import tempfile
import unittest
from pathlib import Path
from unittest import mock

from autoclicker import macro


class FakeKey:
    def __init__(self, text, char=None):
        self.text = text
        self.char = char

    def __str__(self):
        return self.text


class MacroFormatTests(unittest.TestCase):
    def test_round_trip(self):
        actions = [{"type": "key", "action": "press", "key": "a", "delay_ms": 12}]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "shared.akp"
            macro.save_macro(actions, path, name="Test")
            payload = macro.load_macro(path)
        self.assertEqual(payload["name"], "Test")
        self.assertEqual(payload["actions"], actions)

    def test_checksum_rejects_modified_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "shared.akp"
            macro.save_macro([], path)
            data = bytearray(path.read_bytes())
            data[10] ^= 1
            path.write_bytes(data)
            with self.assertRaises(macro.MacroFormatError):
                macro.load_macro(path)

    def test_foreign_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "foreign.akp"
            path.write_bytes(b"not an AutoKeyPresser macro")
            with self.assertRaises(macro.MacroFormatError):
                macro.load_macro(path)


class MacroInputTests(unittest.TestCase):
    def test_key_names(self):
        self.assertEqual(macro.key_to_name(FakeKey("Key.f12")), "f12")
        self.assertEqual(macro.key_to_name(FakeKey("KeyCode", char="A")), "a")
        self.assertIsNone(macro.key_to_name(FakeKey("unknown")))

    def test_player_replays_key_actions(self):
        actions = [
            {"type": "key", "action": "press", "key": "a", "delay_ms": 0},
            {"type": "key", "action": "release", "key": "a", "delay_ms": 0},
        ]
        with mock.patch("autoclicker.macro.pyautogui.keyDown") as down, \
             mock.patch("autoclicker.macro.pyautogui.keyUp") as up:
            player = macro.MacroPlayer(actions, 1, False, lambda _message: None)
            player.start()
            thread = player._thread
            thread.join(timeout=2)
        down.assert_called_once_with("a")
        up.assert_called_once_with("a")


if __name__ == "__main__":
    unittest.main()
