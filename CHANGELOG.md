# Changelog

All notable changes to AutoKeyPresser are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Entries for versions 1.0 through 2.0 were reconstructed on 2026-11-19 from the
published GitHub release notes and the repository history.

## [Unreleased]

### Added

- Text mode beside Mouse and Keyboard in the Action card. A whole printable string is
  sent through `pyautogui.write` as one action, so typing a sentence, a URL, or a
  command line is a single step instead of one key press per character. Text actions
  are stored as an optional `"text"` field in profiles and saved settings, so existing
  profiles and configuration files load unchanged.
- Start delay of 0 to 30 seconds in the run plan, with a live countdown in the run
  card. The wait happens inside the engine before the first action, so it applies to
  a hotkey start as well as the Start button, and Stop or F12 during the countdown
  ends the run without sending anything. The delay is saved as `"start_delay_s"` and
  defaults to `"0"`, which keeps the previous timing exactly.
- Step editor in the profile dialog, replacing the read-only detail pane. A profile's
  steps are listed in order, and Move up, Move down, Remove, and Replace with current
  action change that list in place; Save steps writes it back. The dialog shows
  whether the list matches what is on disk, and Close or Escape asks before discarding
  edits and never writes them. Save current now asks before it replaces a profile's
  stored steps with the action card, so a sequence is not shrunk by one click. Profiles
  keep their existing `"actions"` list on disk, so saved profiles load in older builds
  unchanged.
- A delay of its own for any profile step, set in the step editor's Step delay field.
  A step that carries `"delay_ms"` waits that long before the next step instead of the
  global interval, so a sequence can click, pause two seconds, and then type without
  being recorded as a macro. Steps without the field keep the global interval exactly
  as before, and the key is simply absent from old profiles, so no conversion step is
  needed and older builds ignore it. The list names the pause, as in
  `2. Key B · then waits 2000 ms`.
- Stop after in the run plan: an until-stopped run can be given a duration in minutes and
  ends itself at that deadline, with Stop or F12 still ending it sooner. The deadline is
  checked on the same pause that paces the loop, so a run stops on time even when the
  interval or a step delay is longer than the time left, and it never waits out a pause
  it will not use. The final `done` message is the one a manual stop sends; the status
  line names the limit as the reason (`Stopped · 45 min limit · 1200 actions`). The clock
  starts when the actions begin, so a start delay is not counted against the limit. An
  exact-count run ignores it entirely. The value is saved as `"stop_after_min"` and
  defaults to `"0"`, which means no limit.
- Startup notice when input automation cannot work on this PC. A Wayland session is
  now reported at launch with what actually fails (keys and clicks from this app do
  not reach native Wayland windows, and the global hotkey and F12 only see X11
  windows there), with the note that an app running under XWayland still receives
  input, and with the fix when the target is a Wayland app: log out and pick an
  Xorg or X11 session at the login screen. macOS without the
  Accessibility permission is reported the same way, naming System Settings >
  Privacy & Security > Accessibility for Start, with Input Monitoring mentioned
  only for the hotkey and macro recorder. The check reads `XDG_SESSION_TYPE` and
  the macOS trust answer through `ctypes`, both standard library, and shows a
  single dismissible notice that never blocks the window; Windows, X11, and any
  session it cannot read stay silent, so a failed check never raises a false alarm.

### Fixed

- A run with a "Stop after" limit could send one extra action past the deadline on
  Windows. The pause between actions is clamped to the time left, but Windows'
  `threading.Event.wait` truncates its timeout to whole milliseconds, so the pause
  returned up to a tick before the deadline and the engine read that as "not yet
  reached" and started the next step of the cycle. The deadline now counts as reached
  within one timer tick of slack, so nothing but the action in flight passes it.

## [2.0] - 2026-09-16

### Added

- Aurora theme as the new default, with refreshed palettes for the existing built-in
  themes.
- Live run-plan summary in the action, timing, and run-plan workspace.

### Changed

- Redesigned the desktop workspace along with the profile, appearance, hotkey, help,
  and macro controls.
- Clearer running, stopped, recording, and emergency-stop states.
- Hold duration and randomized interval settings now persist between launches.
- Updated installer and package-manager metadata for version 2.0.
- Existing `.akp` macros, `.akpt` themes, profiles, and saved settings load unchanged.

## [1.6] - 2026-08-15

### Added

- Five built-in themes: Classic Gray, Midnight, Ocean, Forest, and Sunset.
- Live theme selector with apply, import, export, and a remembered selection.
- Proprietary `.akpt` theme files with signature, version, colour and font
  validation, and SHA-256 integrity checks, plus a Windows file association.
- `THEMING.md` and the complete GitHub Wiki documentation set.

### Changed

- Updated package-manager manifests and cross-platform CI release validation.

## [1.5] - 2026-08-15

### Added

- Keyboard and mouse macro recorder with playback of recorded timing.
- Proprietary `.akp` macro files with signature, version, and SHA-256 validation,
  plus a Windows file association.
- GitHub Actions CI across Windows, Linux, and macOS, with automated release builds
  for the portable and installer packages.
- Contributor, security-report, and issue-template files.
- Package-manager manifests for winget, Chocolatey, Scoop, Homebrew, and the AUR.

## [1.4] - 2026-08-15

### Fixed

- Removed PyAutoGUI's default 100 ms pause between calls, so zero and low interval
  settings run at the configured speed instead of stalling near 10 actions per second.

## [1.3] - 2026-08-15

### Added

- F12 emergency stop that always halts active input.
- Hold mode for keyboard keys and mouse buttons with a configurable hold duration.
- Randomized interval mode with minimum and maximum values and range validation.

### Changed

- Update checks and installer metadata synchronised to version 1.3.

## [1.2] - 2026-08-15

### Added

- Saved profiles with a profile manager for save, load, and delete.
- Multiple keyboard and mouse actions in one sequence, with a sequence runner
  supporting repeat counts.
- Profile data stored in the user AutoKeyPresser configuration directory.

## [1.1] - 2026-08-15

### Added

- Background GitHub release update checks with an in-app prompt for newer versions.
- Windows installer download and launch flow, with a release-page fallback on Linux
  and macOS.

## [1.0] - 2026-08-15

### Added

- First public release: intervals from milliseconds to hours, keyboard keys with
  Ctrl, Shift, Alt, and Win/Cmd modifiers, left, right, and middle mouse buttons,
  single and double presses.
- Fixed repeat counts or repeat until stopped, with the live cursor or a fixed X/Y
  coordinate.
- Configurable global start/stop hotkey, F6 by default.
- Portable and installer builds for Windows, Linux, and macOS.

[Unreleased]: https://github.com/CamjamPNG/autokeypresser/compare/v2.0...HEAD
[2.0]: https://github.com/CamjamPNG/autokeypresser/compare/v1.6...v2.0
[1.6]: https://github.com/CamjamPNG/autokeypresser/compare/v1.5...v1.6
[1.5]: https://github.com/CamjamPNG/autokeypresser/compare/v1.4...v1.5
[1.4]: https://github.com/CamjamPNG/autokeypresser/compare/v1.3...v1.4
[1.3]: https://github.com/CamjamPNG/autokeypresser/compare/v1.2...v1.3
[1.2]: https://github.com/CamjamPNG/autokeypresser/compare/v1.1...v1.2
[1.1]: https://github.com/CamjamPNG/autokeypresser/compare/v1.0...v1.1
[1.0]: https://github.com/CamjamPNG/autokeypresser/releases/tag/v1.0
