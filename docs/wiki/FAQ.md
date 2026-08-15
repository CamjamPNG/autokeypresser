# FAQ

## Does `.akp` work in other automation tools?

No. It is validated as an AutoKeyPresser macro file and is not a generic
automation interchange format.

## Does `.akpt` hide theme contents?

No. It uses a signature and checksum for validation, not encryption.

## Why does Linux need X11?

The current global input backend uses X11. Wayland support requires a separate
portal or compositor-specific implementation.
