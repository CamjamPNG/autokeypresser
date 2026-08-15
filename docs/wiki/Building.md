# Building

Install Python, dependencies, and PyInstaller, then use the platform build
script. GitHub Actions runs tests on all three operating systems and creates
release assets when a `v*` tag is pushed.

```text
python -m unittest discover -s tests -v
python -m compileall -q main.py autoclicker tests scripts
```
