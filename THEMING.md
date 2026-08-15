# AutoKeyPresser Themes

AutoKeyPresser 1.6 includes five built-in themes and supports shareable
`.akpt` theme files.

## Built-In Themes

- Classic Gray
- Midnight
- Ocean
- Forest
- Sunset

Select a theme from the **Theme (.akpt)** panel and press **Apply**.

## Custom Theme Format

An `.akpt` file is an AutoKeyPresser Theme file. It contains an AutoKeyPresser
signature, format version, JSON payload, and SHA-256 checksum. AutoKeyPresser
rejects files with invalid signatures, unsupported versions, invalid colors,
or failed checksums.

The payload uses this shape:

```json
{
  "format": "AutoKeyPresser Theme",
  "version": 1,
  "name": "My Theme",
  "author": "Your name",
  "colors": {
    "window": "#202124",
    "panel": "#292a2d",
    "input": "#17181a",
    "text": "#f5f7fa",
    "muted_text": "#b8bcc4",
    "accent": "#4ea1ff",
    "accent_text": "#ffffff",
    "border": "#555a64",
    "disabled": "#3a3d42",
    "danger": "#ff6b6b"
  },
  "font": {
    "family": "TkDefaultFont",
    "size": 9
  }
}
```

Colors must be six-digit hexadecimal values such as `#4ea1ff`. Font sizes
must be between 6 and 32. Use **Export...** to create a correctly signed file;
do not edit the binary file manually.

## Sharing

Use **Export...** to save a theme, then send the `.akpt` file to another
AutoKeyPresser user. They can use **Import...** to validate and install it.
The checksum protects file integrity. It is not encryption and should not be
used to store secrets.
