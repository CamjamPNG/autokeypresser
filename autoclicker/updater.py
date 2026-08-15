import json
import os
import platform
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

CURRENT_VERSION = "1.6"
REPOSITORY = "CamjamPNG/autokeypresser"
RELEASES_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases/latest"


def _version_tuple(value):
    parts = value.lstrip("v").split(".")
    return tuple(int(part) for part in parts[:3])


def is_newer(version):
    try:
        return _version_tuple(version) > _version_tuple(CURRENT_VERSION)
    except (TypeError, ValueError):
        return False


def check_latest_release(timeout=4):
    request = urllib.request.Request(
        RELEASES_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "AutoKeyPresser"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        release = json.loads(response.read().decode("utf-8"))
    return release if is_newer(release.get("tag_name", "")) else None


def installer_asset(release):
    if platform.system() != "Windows":
        return None
    for asset in release.get("assets", []):
        if asset.get("name") == "AutoKeyPresser-Setup.exe":
            return asset.get("browser_download_url")
    return None


def download_installer(url):
    target = Path(tempfile.gettempdir()) / "AutoKeyPresser-update.exe"
    urllib.request.urlretrieve(url, target)
    return target


def launch_installer(path):
    if sys.platform != "win32":
        raise RuntimeError("The Windows installer cannot run on this platform.")
    subprocess.Popen([os.fspath(path)], close_fds=True)
