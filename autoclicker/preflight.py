"""Decide at startup whether this session can actually send input.

The engine talks to the operating system through pyautogui, which needs an X11
session on Linux and the Accessibility permission on macOS. When neither is
available the app still opens, still accepts Start, and silently sends nothing.
This module answers one question - can input work here? - from plain inputs so
the decision is testable anywhere, and reads the real host state in a thin probe
around it.
"""

import ctypes
import os
import sys
from dataclasses import dataclass

SUPPORTED = "supported"
UNSUPPORTED = "unsupported"
UNKNOWN = "unknown"

TITLE = "Input automation is not available"

WAYLAND_MESSAGE = (
    "This Linux session runs Wayland, and AutoKeyPresser sends input through "
    "X11, so its keys and clicks do not reach native Wayland windows.\n\n"
    "If the app you automate is an X11 app itself - a Wine or Proton game, a "
    "Java app - XWayland delivers the input to it, so there is nothing to "
    "fix.\n\n"
    "Fix: if the app you automate is a Wayland app, log out and choose an Xorg "
    "or X11 session at the login screen (on Ubuntu, the gear menu beside Sign "
    "in), then start AutoKeyPresser again. Newer GNOME and KDE releases can "
    "forward input to Wayland windows as well, once you approve their one-time "
    "remote-interaction prompt.\n\n"
    "Either way the global hotkey and the F12 emergency stop only see X11 "
    "windows on Wayland, so stop a run from this window rather than relying on "
    "them."
)

MACOS_MESSAGE = (
    "macOS has not granted AutoKeyPresser the Accessibility permission, so "
    "Start will run and nothing will be sent.\n\n"
    "Fix: open System Settings > Privacy & Security > Accessibility and turn "
    "AutoKeyPresser on, then quit and reopen the app. If you start the app from "
    "a terminal, grant that terminal the permission instead. If the global "
    "hotkey or the macro recorder does nothing, also allow it under Privacy & "
    "Security > Input Monitoring."
)

# Loading the framework, not the call into it, is what fails on a macOS build
# that has no ApplicationServices - both are reported as one of these.
_FRAMEWORK = (
    "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
)
_PROBE_ERRORS = (OSError, AttributeError, TypeError, ValueError, ctypes.ArgumentError)


@dataclass(frozen=True)
class Preflight:
    """What the probe learned, and the one message worth showing for it."""

    state: str
    message: str = ""

    @property
    def warns(self):
        return self.state == UNSUPPORTED


def assess(platform, session_type=None, accessibility_trusted=None):
    """Decide from explicit inputs, so the rules hold on any machine.

    platform is a sys.platform value, session_type is XDG_SESSION_TYPE as the
    desktop set it, and accessibility_trusted is what macOS reported. Anything
    this cannot read is UNKNOWN, which stays quiet: guessing either way would
    either hide a real problem or invent one.
    """
    if platform == "win32":
        return Preflight(SUPPORTED)
    if platform == "darwin":
        if accessibility_trusted is True:
            return Preflight(SUPPORTED)
        if accessibility_trusted is False:
            return Preflight(UNSUPPORTED, MACOS_MESSAGE)
        return Preflight(UNKNOWN)
    if isinstance(platform, str) and platform.startswith("linux"):
        session = session_type.strip().lower() if isinstance(session_type, str) else ""
        if session == "x11":
            return Preflight(SUPPORTED)
        if session.startswith("wayland"):
            return Preflight(UNSUPPORTED, WAYLAND_MESSAGE)
        # tty, mir, unset, or a value a compositor invented: say nothing.
        return Preflight(UNKNOWN)
    return Preflight(UNKNOWN)


def _macos_accessibility_trusted():
    """True or False from AXIsProcessTrusted, or None when it cannot be read."""
    try:
        framework = ctypes.cdll.LoadLibrary(_FRAMEWORK)
        check = framework.AXIsProcessTrusted
        check.restype = ctypes.c_bool
        check.argtypes = []
        return bool(check())
    except _PROBE_ERRORS:
        return None


def probe(platform=None, environ=None, accessibility_trust=None):
    """Read this host and hand it to assess(). Never raises for a failed read.

    The probe is deliberately thin: it only reaches the host for the two facts
    assess() needs, and every failure in reaching them becomes UNKNOWN rather
    than an exception at startup.
    """
    if platform is None:
        platform = sys.platform
    if platform == "darwin":
        trust = accessibility_trust if accessibility_trust is not None else _macos_accessibility_trusted
        try:
            trusted = trust()
        except _PROBE_ERRORS:
            trusted = None
        return assess(platform, accessibility_trusted=trusted)
    if isinstance(platform, str) and platform.startswith("linux"):
        env = os.environ if environ is None else environ
        return assess(platform, session_type=env.get("XDG_SESSION_TYPE"))
    return assess(platform)


def startup_notice(platform=None, environ=None, accessibility_trust=None):
    """The warning to show once at launch, or None when there is nothing to say."""
    result = probe(platform=platform, environ=environ, accessibility_trust=accessibility_trust)
    return result if result.warns else None
