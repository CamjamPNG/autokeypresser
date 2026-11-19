import unittest
from unittest import mock

import autoclicker.engine as engine_module
from autoclicker.engine import PressEngine, PressSettings


def make_engine(**overrides):
    settings = PressSettings()
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


class PressEngineTests(unittest.TestCase):
    def test_start_disables_pyautogui_default_pause(self):
        settings = make_engine(repeat_until_stopped=False, repeat_count=1, interval_seconds=0)
        with mock.patch("autoclicker.engine.pyautogui.click") as click:
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            thread = engine._thread
            thread.join(timeout=2)
        self.assertEqual(click.call_count, 1)
        self.assertEqual(engine.count, 1)
        self.assertEqual(engine.settings.interval_seconds, 0)
        self.assertEqual(engine_module.pyautogui.PAUSE, 0)

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

    def test_action_sequence_repeats_as_cycles(self):
        settings = make_engine(
            repeat_until_stopped=False,
            repeat_count=2,
            interval_seconds=0,
            actions=[
                {"input_type": "keyboard", "key": "a", "modifiers": [], "click_type": "single"},
                {"input_type": "keyboard", "key": "b", "modifiers": [], "click_type": "single"},
            ],
        )
        with mock.patch("autoclicker.engine.pyautogui.press") as press:
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            thread = engine._thread
            thread.join(timeout=2)
        self.assertEqual(engine.count, 4)
        self.assertEqual([call.args[0] for call in press.call_args_list], ["a", "b", "a", "b"])

    def test_text_action_writes_whole_string_in_one_call(self):
        settings = make_engine(
            input_type="text", text="Hello, world! (v2.0.1)",
            repeat_until_stopped=False, repeat_count=1, interval_seconds=0,
        )
        with mock.patch("autoclicker.engine.pyautogui.write") as write, \
             mock.patch("autoclicker.engine.pyautogui.press") as press, \
             mock.patch("autoclicker.engine.pyautogui.click") as click:
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            thread = engine._thread
            thread.join(timeout=2)
        write.assert_called_once_with("Hello, world! (v2.0.1)")
        press.assert_not_called()
        click.assert_not_called()
        self.assertEqual(engine.count, 1)

    def test_text_action_repeats_once_per_action(self):
        settings = make_engine(
            input_type="text", text="ping 10.0.0.1",
            repeat_until_stopped=False, repeat_count=3, interval_seconds=0,
        )
        with mock.patch("autoclicker.engine.pyautogui.write") as write:
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            thread = engine._thread
            thread.join(timeout=2)
        self.assertEqual([call.args[0] for call in write.call_args_list], ["ping 10.0.0.1"] * 3)
        self.assertEqual(engine.count, 3)

    def test_text_action_runs_beside_keys_in_a_sequence(self):
        settings = make_engine(
            repeat_until_stopped=False,
            repeat_count=1,
            interval_seconds=0,
            actions=[
                {"input_type": "text", "text": "git status"},
                {"input_type": "keyboard", "key": "enter", "modifiers": [], "click_type": "single"},
            ],
        )
        with mock.patch("autoclicker.engine.pyautogui.write") as write, \
             mock.patch("autoclicker.engine.pyautogui.press") as press:
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            thread = engine._thread
            thread.join(timeout=2)
        write.assert_called_once_with("git status")
        press.assert_called_once_with("enter")
        self.assertEqual(engine.count, 2)

    def test_text_action_ignores_hold_mode(self):
        settings = make_engine(
            input_type="text", text="held?", hold_mode=True, hold_duration_seconds=5,
            repeat_until_stopped=False, repeat_count=1, interval_seconds=0,
        )
        with mock.patch("autoclicker.engine.pyautogui.write") as write, \
             mock.patch("autoclicker.engine.pyautogui.keyDown") as down:
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            thread = engine._thread
            thread.join(timeout=2)
        write.assert_called_once_with("held?")
        down.assert_not_called()

    def test_hold_keyboard_uses_key_down_and_up(self):
        settings = make_engine(
            input_type="keyboard", key="a", hold_mode=True,
            hold_duration_seconds=0.001, repeat_until_stopped=False,
            repeat_count=1, interval_seconds=0,
        )
        with mock.patch("autoclicker.engine.pyautogui.keyDown") as down, \
             mock.patch("autoclicker.engine.pyautogui.keyUp") as up:
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            thread = engine._thread
            thread.join(timeout=2)
        down.assert_called_once_with("a")
        up.assert_called_once_with("a")


if __name__ == "__main__":
    unittest.main()
