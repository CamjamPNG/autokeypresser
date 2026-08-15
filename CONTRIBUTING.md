# Contributing

## Development

```text
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

On Linux and macOS, use `.venv/bin/python` instead.

## Pull requests

- Keep changes focused.
- Add or update tests for behavior changes.
- Run the test suite and compile check before opening a pull request.
- Do not include secrets, generated build folders, or personal configuration.

Feature work should explain the user problem it solves and include screenshots
for visible interface changes.
