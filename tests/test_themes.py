import tempfile
import unittest
from pathlib import Path

from autoclicker import themes


class ThemeTests(unittest.TestCase):
    def test_five_builtin_themes(self):
        self.assertEqual(len(themes.theme_names()), 5)
        for name in themes.theme_names():
            self.assertEqual(themes.make_theme(name)["name"], name)

    def test_round_trip(self):
        theme = themes.make_theme("Midnight")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "midnight.akpt"
            themes.save_theme(theme, path)
            loaded = themes.load_theme(path)
        self.assertEqual(loaded["colors"]["accent"], "#4ea1ff")

    def test_modified_theme_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "broken.akpt"
            themes.save_theme(themes.make_theme("Ocean"), path)
            data = bytearray(path.read_bytes())
            data[12] ^= 1
            path.write_bytes(data)
            with self.assertRaises(themes.ThemeFormatError):
                themes.load_theme(path)

    def test_invalid_color_rejected(self):
        theme = themes.make_theme("Forest")
        theme["colors"]["accent"] = "blue"
        with self.assertRaises(themes.ThemeFormatError):
            themes.validate_theme(theme)
