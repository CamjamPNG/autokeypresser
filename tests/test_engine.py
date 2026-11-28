import threading
import time
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


class StartDelayTests(unittest.TestCase):
    def test_no_input_is_sent_before_the_delay_elapses(self):
        settings = make_engine(
            repeat_until_stopped=False, repeat_count=1, interval_seconds=0,
            start_delay_seconds=0.4,
        )
        clicks = []

        def record(*_args, **_kwargs):
            clicks.append(time.monotonic())

        with mock.patch("autoclicker.engine.pyautogui.click", side_effect=record):
            engine = PressEngine(settings, on_status=lambda _m: None)
            started = time.monotonic()
            engine.start()
            engine._thread.join(timeout=3)

        self.assertEqual(len(clicks), 1)
        self.assertGreaterEqual(clicks[0] - started, 0.35)
        self.assertEqual(engine.count, 1)

    def test_countdown_reports_whole_seconds_and_holds_the_first_action(self):
        settings = make_engine(
            repeat_until_stopped=False, repeat_count=1, interval_seconds=0,
            start_delay_seconds=3,
        )
        statuses = []
        ticked = threading.Event()

        def on_status(message):
            statuses.append(message)
            if message[0] == "countdown":
                ticked.set()

        with mock.patch("autoclicker.engine.pyautogui.click") as click:
            engine = PressEngine(settings, on_status=on_status)
            engine.start()
            self.assertTrue(ticked.wait(2))
            click.assert_not_called()
            engine.stop()
            engine._thread.join(timeout=2)

        self.assertEqual(statuses[0], ("countdown", 3))

    def test_stopping_during_the_countdown_ends_the_run_cleanly(self):
        settings = make_engine(
            repeat_until_stopped=True, interval_seconds=0, start_delay_seconds=5
        )
        statuses = []
        ticked = threading.Event()

        def on_status(message):
            statuses.append(message)
            if message[0] == "countdown":
                ticked.set()

        with mock.patch("autoclicker.engine.pyautogui.click") as click, \
             mock.patch("autoclicker.engine.pyautogui.press") as press:
            engine = PressEngine(settings, on_status=on_status)
            engine.start()
            self.assertTrue(ticked.wait(2))
            engine.stop()
            engine._thread.join(timeout=2)

        self.assertFalse(engine.running)
        self.assertEqual(engine.count, 0)
        click.assert_not_called()
        press.assert_not_called()
        self.assertEqual(statuses[-1], ("done", 0))

    def test_zero_delay_skips_the_countdown_entirely(self):
        settings = make_engine(
            repeat_until_stopped=False, repeat_count=1, interval_seconds=0
        )
        statuses = []
        with mock.patch("autoclicker.engine.pyautogui.click") as click:
            engine = PressEngine(settings, on_status=statuses.append)
            engine.start()
            engine._thread.join(timeout=2)

        self.assertEqual(click.call_count, 1)
        self.assertFalse(any(msg == "countdown" for msg, _ in statuses))


class PerStepDelayTests(unittest.TestCase):
    """A step that carries delay_ms waits its own value instead of the interval."""

    def engine(self, **overrides):
        return PressEngine(make_engine(**overrides), on_status=lambda _m: None)

    def test_a_step_without_a_delay_keeps_the_global_interval(self):
        engine = self.engine(interval_seconds=0.25)

        self.assertEqual(engine._next_interval(0.25), 0.25)
        self.assertEqual(engine._next_interval(0.25, {"input_type": "keyboard"}), 0.25)

    def test_a_step_with_a_delay_waits_its_own_value(self):
        engine = self.engine(interval_seconds=0.25)

        self.assertAlmostEqual(engine._next_interval(0.25, {"delay_ms": 2000}), 2.0)
        self.assertAlmostEqual(engine._next_interval(0.25, {"delay_ms": 0}), 0.001)

    def test_an_infinite_delay_falls_back_instead_of_raising(self):
        engine = self.engine(interval_seconds=0.25)

        self.assertEqual(engine._next_interval(0.25, {"delay_ms": float("inf")}), 0.25)
        self.assertEqual(engine._next_interval(0.25, {"delay_ms": "1e400"}), 0.25)
        self.assertEqual(engine._next_interval(0.25, {"delay_ms": float("nan")}), 0.25)

    def test_a_step_delay_wins_over_a_randomized_interval(self):
        engine = self.engine(
            interval_seconds=0.25,
            randomize_interval=True,
            random_min_seconds=0.5,
            random_max_seconds=0.9,
        )

        self.assertAlmostEqual(engine._next_interval(0.25, {"delay_ms": 40}), 0.04)
        self.assertTrue(0.5 <= engine._next_interval(0.25, {}) <= 0.9)

    def test_the_run_waits_the_per_step_delay_between_presses(self):
        settings = make_engine(
            input_type="keyboard",
            key="a",
            interval_seconds=0,
            repeat_until_stopped=False,
            repeat_count=1,
        )
        settings.actions = [
            {"input_type": "keyboard", "key": "a", "delay_ms": 200},
            {"input_type": "keyboard", "key": "b"},
        ]
        pressed = []

        def record(key):
            pressed.append((key, time.monotonic()))

        with mock.patch("autoclicker.engine.pyautogui.press", side_effect=record):
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            engine._thread.join(timeout=3)

        self.assertEqual([key for key, _ in pressed], ["a", "b"])
        gap = pressed[1][1] - pressed[0][1]
        self.assertGreaterEqual(gap, 0.18)
        self.assertLess(gap, 0.5)

    def test_the_run_uses_the_global_interval_for_a_step_without_a_delay(self):
        settings = make_engine(
            input_type="keyboard",
            key="a",
            interval_seconds=0.1,
            repeat_until_stopped=False,
            repeat_count=2,
        )
        settings.actions = [{"input_type": "keyboard", "key": "a"}]
        pressed = []

        def record(key):
            pressed.append((key, time.monotonic()))

        with mock.patch("autoclicker.engine.pyautogui.press", side_effect=record):
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            engine._thread.join(timeout=3)

        self.assertEqual(len(pressed), 2)
        gap = pressed[1][1] - pressed[0][1]
        self.assertGreaterEqual(gap, 0.08)
        self.assertLess(gap, 0.35)

    def test_a_run_does_not_wait_after_its_final_press(self):
        settings = make_engine(
            input_type="keyboard",
            key="a",
            interval_seconds=0,
            repeat_until_stopped=False,
            repeat_count=1,
        )
        settings.actions = [{"input_type": "keyboard", "key": "a", "delay_ms": 500}]
        started = time.monotonic()

        with mock.patch("autoclicker.engine.pyautogui.press"):
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            engine._thread.join(timeout=3)

        self.assertEqual(engine.count, 1)
        self.assertLess(time.monotonic() - started, 0.3)

    def test_a_delay_still_paces_a_step_that_is_not_last(self):
        settings = make_engine(
            input_type="keyboard",
            key="a",
            interval_seconds=0,
            repeat_until_stopped=False,
            repeat_count=2,
        )
        settings.actions = [
            {"input_type": "keyboard", "key": "a", "delay_ms": 120},
            {"input_type": "keyboard", "key": "b"},
        ]
        pressed = []

        def record(key):
            pressed.append((key, time.monotonic()))

        with mock.patch("autoclicker.engine.pyautogui.press", side_effect=record):
            engine = PressEngine(settings, on_status=lambda _m: None)
            engine.start()
            engine._thread.join(timeout=3)

        self.assertEqual([key for key, _ in pressed], ["a", "b", "a", "b"])
        first_gap = pressed[1][1] - pressed[0][1]
        second_gap = pressed[3][1] - pressed[2][1]
        self.assertGreaterEqual(first_gap, 0.10)
        self.assertLess(first_gap, 0.35)
        self.assertGreaterEqual(second_gap, 0.10)
        self.assertLess(second_gap, 0.35)


class StopAfterTests(unittest.TestCase):
    """An until-stopped run ends itself at its deadline and says so."""

    def run_engine(self, timeout=5, **overrides):
        settings = make_engine(**overrides)
        statuses = []
        with mock.patch("autoclicker.engine.pyautogui.click"):
            engine = PressEngine(settings, on_status=statuses.append)
            started = time.monotonic()
            engine.start()
            engine._thread.join(timeout=timeout)
            elapsed = time.monotonic() - started
        return engine, statuses, elapsed

    def limit_messages(self, statuses):
        return [value for msg, value in statuses if msg == "limit"]

    def test_the_run_ends_at_the_deadline_and_still_reports_done(self):
        engine, statuses, elapsed = self.run_engine(
            repeat_until_stopped=True, interval_seconds=0.02, stop_after_seconds=0.6
        )

        self.assertFalse(engine.running)
        # A band, not just "it stopped": the deadline is 0.6 s, so a run that
        # ignored the limit, or read it as minutes, lands far outside this.
        self.assertGreaterEqual(elapsed, 0.55)
        self.assertLess(elapsed, 1.6)
        self.assertGreater(engine.count, 1)
        self.assertEqual(statuses[-1], ("done", engine.count))

    def test_the_limit_is_reported_before_the_final_done(self):
        _, statuses, _ = self.run_engine(
            repeat_until_stopped=True, interval_seconds=0.02, stop_after_seconds=1
        )

        self.assertEqual(self.limit_messages(statuses), [1])
        self.assertLessEqual(statuses.index(("limit", 1)), len(statuses) - 1)
        self.assertEqual(statuses[-1][0], "done")

    def test_a_manual_stop_before_the_deadline_wins(self):
        settings = make_engine(
            repeat_until_stopped=True, interval_seconds=0.02, stop_after_seconds=30
        )
        statuses = []
        with mock.patch("autoclicker.engine.pyautogui.click"):
            engine = PressEngine(settings, on_status=statuses.append)
            started = time.monotonic()
            engine.start()
            time.sleep(0.15)
            engine.stop()
            engine._thread.join(timeout=3)
            elapsed = time.monotonic() - started

        self.assertFalse(engine.running)
        self.assertLess(elapsed, 1.5)
        self.assertEqual(statuses[-1], ("done", engine.count))
        self.assertEqual(self.limit_messages(statuses), [])

    def test_an_exact_count_run_ignores_the_limit(self):
        engine, statuses, elapsed = self.run_engine(
            repeat_until_stopped=False,
            repeat_count=3,
            interval_seconds=0.1,
            stop_after_seconds=0.05,
        )

        self.assertEqual(engine.count, 3)
        self.assertGreaterEqual(elapsed, 0.15)
        self.assertEqual(statuses[-1], ("done", 3))
        self.assertEqual(self.limit_messages(statuses), [])

    def test_an_exact_count_run_still_finishes_immediately(self):
        engine, statuses, elapsed = self.run_engine(
            repeat_until_stopped=False,
            repeat_count=2,
            interval_seconds=0,
            stop_after_seconds=3600,
        )

        self.assertEqual(engine.count, 2)
        # A count run ignores the 3600 s deadline, so a run that failed to end
        # at its count is still going at the join timeout. The bound stays far
        # under that and far over any thread-start overhead on a loaded runner.
        self.assertLess(elapsed, 2.0)
        self.assertEqual(statuses[-1], ("done", 2))

    def test_the_start_delay_is_not_counted_against_the_limit(self):
        engine, statuses, elapsed = self.run_engine(
            repeat_until_stopped=True,
            interval_seconds=0.02,
            start_delay_seconds=0.5,
            stop_after_seconds=1,
        )

        # 0.5 s of waiting plus 1 s of pressing, so the limit cannot start at
        # Start: a clock that did would stop the run before it pressed at all.
        self.assertGreaterEqual(elapsed, 1.4)
        self.assertLess(elapsed, 2.5)
        self.assertGreater(engine.count, 0)
        self.assertEqual(self.limit_messages(statuses), [1])

    def test_the_limit_does_not_wait_out_a_long_pause(self):
        _, statuses, elapsed = self.run_engine(
            repeat_until_stopped=True, interval_seconds=5, stop_after_seconds=0.4
        )

        self.assertLess(elapsed, 2.0)
        self.assertEqual(statuses[-1][0], "done")
        self.assertEqual(self.limit_messages(statuses), [0])

    def test_a_long_step_delay_does_not_overshoot_the_deadline(self):
        settings = make_engine(
            input_type="keyboard",
            interval_seconds=0,
            repeat_until_stopped=True,
            stop_after_seconds=0.4,
        )
        settings.actions = [
            {"input_type": "keyboard", "key": "a", "delay_ms": 5000},
            {"input_type": "keyboard", "key": "b"},
        ]
        statuses = []
        with mock.patch("autoclicker.engine.pyautogui.press"):
            engine = PressEngine(settings, on_status=statuses.append)
            started = time.monotonic()
            engine.start()
            engine._thread.join(timeout=3)
            elapsed = time.monotonic() - started

        # The clamped pause ends the run at the deadline, so the second action
        # of that cycle never runs: at most the action in flight goes past it.
        # The bound sits well under the 5000 ms step delay, so an unclamped
        # pause still fails here, and well over any scheduling delay a loaded
        # runner adds: this asserts the clamp, not that the machine was quick.
        self.assertEqual(engine.count, 1)
        self.assertGreaterEqual(elapsed, 0.35)
        self.assertLess(elapsed, 2.5)
        self.assertEqual(statuses[-1], ("done", 1))

    def test_a_randomized_interval_does_not_overshoot_the_deadline(self):
        _, _, elapsed = self.run_engine(
            repeat_until_stopped=True,
            interval_seconds=0.02,
            randomize_interval=True,
            random_min_seconds=2.0,
            random_max_seconds=3.0,
            stop_after_seconds=0.3,
        )

        self.assertLess(elapsed, 1.2)

    def test_a_zero_or_unreadable_limit_means_no_deadline(self):
        for seconds in (0, 0.0, None, -5, float("inf"), float("nan"), "soon"):
            engine = PressEngine(
                make_engine(repeat_until_stopped=True, stop_after_seconds=seconds),
                on_status=lambda _m: None,
            )
            self.assertIsNone(engine._deadline(), seconds)

    def test_a_count_run_has_no_deadline(self):
        engine = PressEngine(
            make_engine(
                repeat_until_stopped=False, repeat_count=2, stop_after_seconds=60
            ),
            on_status=lambda _m: None,
        )

        self.assertIsNone(engine._deadline())


class StopAfterReviewFixTests(unittest.TestCase):
    """The two guards the PR #7 audit asked for."""

    def test_the_limit_message_uses_the_value_the_deadline_was_taken_from(self):
        settings = make_engine(
            repeat_until_stopped=True, interval_seconds=0.02, stop_after_seconds=1
        )
        statuses = []
        with mock.patch("autoclicker.engine.pyautogui.click"):
            engine = PressEngine(settings, on_status=statuses.append)
            started = time.monotonic()
            engine.start()
            time.sleep(0.2)
            # The UI collects settings in place, so a field edited mid-run must
            # not rewrite what the status line says ended it.
            settings.stop_after_seconds = 0
            engine._thread.join(timeout=3)
            elapsed = time.monotonic() - started

        self.assertGreaterEqual(elapsed, 0.95)
        self.assertLess(elapsed, 2.0)
        self.assertEqual([value for msg, value in statuses if msg == "limit"], [1])
        self.assertEqual(statuses[-1], ("done", engine.count))


if __name__ == "__main__":
    unittest.main()
