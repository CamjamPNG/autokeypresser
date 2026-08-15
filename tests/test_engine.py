import unittest
from unittest import mock

from autoclicker.engine import PressEngine, PressSettings


def make_engine(**overrides):
    settings = PressSettings()
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


class PressEngineTests(unittest.TestCase):
    def test_repeat_count_stops_after_n(self):
        settings = make_engine(repeat_until_stopped=False, repeat_count=3, interval_seconds=0)
        statuses = []
        with mock.patch("autoclicker.engine.pyautogui.click") as click:
            engine = PressEngine(settings, on_status=statuses.append)
            engine.start()
            thread = engine._thread
            thread.join(timeout=2)
        self.assertFalse(engine.running)
        self.assertEqual(engine.count, 3)
        self.assertEqual(click.call_count, 3)
        self.assertTrue(any(msg == "done" for msg, _ in statuses))

    def test_stop_halts_infinite_loop(self):
        settings = make_engine(repeat_until_stopped=True, interval_seconds=0.01)
        statuses = []
        with mock.patch("autoclicker.engine.pyautogui.click") as click:
            engine = PressEngine(settings, on_status=statuses.append)
            engine.start()
            engine.stop()
            engine._thread.join(timeout=2)
        self.assertFalse(engine.running)
        self.assertGreater(engine.count, 0)
        self.assertTrue(any(msg == "done" for msg, _ in statuses))

    def test_keyboard_single_press(self):
        settings = make_engine(
            input_type="keyboard", key="a", modifiers=[],
            repeat_until_stopped=False, repeat_count=1, interval_seconds=0,
        )
        with mock.patch("autoclicker.engine.pyautogui.press") as press:
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            thread = engine._thread
            thread.join(timeout=2)
        press.assert_called_once_with("a")

    def test_keyboard_with_modifier_uses_hotkey(self):
        settings = make_engine(
            input_type="keyboard", key="c", modifiers=["ctrl"],
            repeat_until_stopped=False, repeat_count=1, interval_seconds=0,
        )
        with mock.patch("autoclicker.engine.pyautogui.hotkey") as hotkey:
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            thread = engine._thread
            thread.join(timeout=2)
        hotkey.assert_called_once_with("ctrl", "c")

    def test_mouse_double_click(self):
        settings = make_engine(
            click_type="double", repeat_until_stopped=False,
            repeat_count=1, interval_seconds=0,
        )
        with mock.patch("autoclicker.engine.pyautogui.position", return_value=(5, 5)), \
             mock.patch("autoclicker.engine.pyautogui.click") as click:
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            thread = engine._thread
            thread.join(timeout=2)
        click.assert_called_once_with(5, 5, clicks=2, interval=0.02, button="left")

    def test_fixed_position_used(self):
        settings = make_engine(
            use_fixed_position=True, fixed_x=100, fixed_y=200,
            repeat_until_stopped=False, repeat_count=1, interval_seconds=0,
        )
        with mock.patch("autoclicker.engine.pyautogui.click") as click:
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            thread = engine._thread
            thread.join(timeout=2)
        click.assert_called_once_with(100, 200, button="left")


if __name__ == "__main__":
    unittest.main()
