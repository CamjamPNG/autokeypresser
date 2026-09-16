# AutoKeyPresser Themes

AutoKeyPresser 2.0 includes six built-in themes and supports shareable
`.akpt` theme files.

## Built-In Themes

- Classic Gray
- Midnight
- Ocean
- Forest
- Sunset
- Aurora

Select a theme from **Appearance** for an instant live preview.

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
    "window": "#0b0d12",
    "panel": "#14171e",
    "input": "#0f1218",
    "text": "#f5f7fb",
    "muted_text": "#929bad",
    "accent": "#64a8ff",
    "accent_text": "#ffffff",
    "border": "#282d38",
    "disabled": "#4c5362",
    "danger": "#ff6673",
    "success": "#45d09e"
  },
  "font": {
    "family": "TkDefaultFont",
    "size": 9
  }
}
```

Colors must be six-digit hexadecimal values such as `#64a8ff`. Font sizes
must be between 6 and 32. Use **Export...** to create a correctly signed file;
do not edit the binary file manually.

## Sharing

Use **Export...** to save a theme, then send the `.akpt` file to another
AutoKeyPresser user. They can use **Import...** to validate and install it.
The checksum protects file integrity. It is not encryption and should not be
used to store secrets.
