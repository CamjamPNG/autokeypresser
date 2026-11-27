import sys
import unittest
from unittest import mock

from autoclicker import preflight
from autoclicker.preflight import SUPPORTED, UNKNOWN, UNSUPPORTED, assess, probe, startup_notice


class AssessTests(unittest.TestCase):
    """The decision comes from inputs, so these hold on any test machine."""

    def test_windows_is_supported(self):
        result = assess("win32")
        self.assertEqual(result.state, SUPPORTED)
        self.assertFalse(result.warns)
        self.assertEqual(result.message, "")

    def test_linux_x11_is_supported(self):
        result = assess("linux", session_type="x11")
        self.assertEqual(result.state, SUPPORTED)
        self.assertFalse(result.warns)
        self.assertEqual(result.message, "")

    def test_linux_x11_ignores_case_and_padding(self):
        self.assertEqual(assess("linux", session_type=" X11 ").state, SUPPORTED)

    def test_wayland_is_unsupported_and_names_the_x11_fix(self):
        result = assess("linux", session_type="wayland")
        self.assertEqual(result.state, UNSUPPORTED)
        self.assertTrue(result.warns)
        self.assertIn("X11", result.message)
        self.assertIn("Xorg", result.message)
        self.assertIn("log out", result.message)

    def test_wayland_variant_is_unsupported(self):
        self.assertEqual(assess("linux", session_type="Wayland").state, UNSUPPORTED)

    def test_macos_with_trust_is_supported(self):
        result = assess("darwin", accessibility_trusted=True)
        self.assertEqual(result.state, SUPPORTED)
        self.assertFalse(result.warns)
        self.assertEqual(result.message, "")

    def test_untrusted_macos_is_unsupported_and_names_the_setting(self):
        result = assess("darwin", accessibility_trusted=False)
        self.assertEqual(result.state, UNSUPPORTED)
        self.assertIn("Accessibility", result.message)
        self.assertIn("System Settings", result.message)
        self.assertIn("Security", result.message)

    def test_macos_without_a_reading_is_unknown_and_silent(self):
        result = assess("darwin", accessibility_trusted=None)
        self.assertEqual(result.state, UNKNOWN)
        self.assertFalse(result.warns)
        self.assertEqual(result.message, "")

    def test_unknown_session_type_is_unknown_and_silent(self):
        for session_type in (None, "", "tty", "mir", "  "):
            with self.subTest(session_type=session_type):
                result = assess("linux", session_type=session_type)
                self.assertEqual(result.state, UNKNOWN)
                self.assertFalse(result.warns)
                self.assertEqual(result.message, "")

    def test_other_platform_is_unknown(self):
        result = assess("freebsd13")
        self.assertEqual(result.state, UNKNOWN)
        self.assertFalse(result.warns)

    def test_every_warning_names_a_concrete_fix(self):
        for result in (assess("linux", session_type="wayland"), assess("darwin", accessibility_trusted=False)):
            with self.subTest(state=result.state):
                self.assertIn("Fix:", result.message)
                self.assertNotIn("may not work", result.message)


class ProbeTests(unittest.TestCase):
    """The probe only reads the host; every failed read is UNKNOWN."""

    def test_linux_reads_the_session_variable(self):
        self.assertEqual(probe("linux", environ={"XDG_SESSION_TYPE": "x11"}).state, SUPPORTED)
        self.assertEqual(
            probe("linux", environ={"XDG_SESSION_TYPE": "wayland"}).state, UNSUPPORTED
        )

    def test_linux_without_the_variable_is_unknown(self):
        self.assertEqual(probe("linux", environ={}).state, UNKNOWN)

    def test_windows_needs_no_lookup(self):
        self.assertEqual(probe("win32").state, SUPPORTED)

    def test_macos_reads_the_trust_callable(self):
        self.assertEqual(probe("darwin", accessibility_trust=lambda: True).state, SUPPORTED)
        self.assertEqual(probe("darwin", accessibility_trust=lambda: False).state, UNSUPPORTED)

    def test_macos_trust_callable_that_raises_is_unknown(self):
        def explode():
            raise OSError("framework unavailable")

        self.assertEqual(probe("darwin", accessibility_trust=explode).state, UNKNOWN)

    @unittest.skipUnless(sys.platform == "darwin", "reads the real macOS framework")
    def test_the_real_framework_reads_on_macos(self):
        """The only check of the live ctypes path: CI's macOS job runs this one."""
        self.assertIn(preflight._macos_accessibility_trusted(), (True, False))

    def test_macos_framework_that_will_not_load_is_unknown(self):
        with mock.patch("ctypes.cdll.LoadLibrary", side_effect=OSError("no framework")):
            self.assertIsNone(preflight._macos_accessibility_trusted())
            self.assertEqual(probe("darwin").state, UNKNOWN)

    def test_probe_never_raises_for_an_odd_environment(self):
        self.assertEqual(probe("linux", environ={"XDG_SESSION_TYPE": None}).state, UNKNOWN)
        self.assertEqual(probe("linux", environ={"XDG_SESSION_TYPE": 11}).state, UNKNOWN)


class StartupNoticeTests(unittest.TestCase):
    def test_supported_sessions_say_nothing(self):
        self.assertIsNone(startup_notice("win32"))
        self.assertIsNone(startup_notice("linux", environ={"XDG_SESSION_TYPE": "x11"}))
        self.assertIsNone(startup_notice("linux", environ={}))

    def test_unsupported_sessions_show_one_message(self):
        wayland = startup_notice("linux", environ={"XDG_SESSION_TYPE": "wayland"})
        self.assertIsNotNone(wayland)
        self.assertEqual(wayland.state, UNSUPPORTED)
        self.assertIn("X11", wayland.message)
        macos = startup_notice("darwin", accessibility_trust=lambda: False)
        self.assertIsNotNone(macos)
        self.assertIn("Accessibility", macos.message)

    def test_unknown_never_renders_as_supported(self):
        unknown = assess("darwin", accessibility_trusted=None)
        self.assertFalse(unknown.warns)
        self.assertNotEqual(unknown.state, SUPPORTED)


if __name__ == "__main__":
    unittest.main()
