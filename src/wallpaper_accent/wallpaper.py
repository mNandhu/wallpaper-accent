"""macOS glue: resolve the current wallpaper image + light/dark appearance."""
from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path

from .config import WALLPAPER_INDEX
from .util import log


def find_wallpaper() -> Path | None:
    """Return the current wallpaper image path, or None if it is not an image.

    Primary source is the wallpaper store's Index.plist (no TCC prompt, works
    under launchd); falls back to AppleScript. Dynamic/aerial/solid-colour
    wallpapers have no backing image file and yield None.
    """
    return _from_index() or _from_osascript()


def _from_index() -> Path | None:
    if not WALLPAPER_INDEX.is_file():
        return None
    try:
        xml = subprocess.check_output(
            ["plutil", "-convert", "xml1", "-o", "-", str(WALLPAPER_INDEX)]
        )
        root = plistlib.loads(xml)
    except Exception as exc:  # noqa: BLE001 - fall back below
        log(f"index parse failed: {exc}")
        return None

    found: list[Path] = []

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)
        elif isinstance(obj, bytes) and obj[:6] == b"bplist":
            try:
                inner = plistlib.loads(obj)
            except Exception:  # noqa: BLE001
                return
            if isinstance(inner, dict) and inner.get("type") == "imageFile":
                url = inner.get("url", {})
                rel = url.get("relative") if isinstance(url, dict) else None
                if isinstance(rel, str) and rel.startswith("file://"):
                    from urllib.parse import unquote, urlparse

                    found.append(Path(unquote(urlparse(rel).path)))

    walk(root)
    return found[0] if found else None


def _from_osascript() -> Path | None:
    try:
        out = subprocess.check_output(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get picture of current desktop',
            ],
            text=True,
        ).strip()
    except Exception as exc:  # noqa: BLE001
        log(f"osascript fallback failed: {exc}")
        return None
    if not out or out == "missing value":
        return None
    return Path(out.split(",")[0].strip())


def is_dark_appearance() -> bool:
    try:
        out = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True,
            text=True,
        )
        return out.returncode == 0 and out.stdout.strip() == "Dark"
    except Exception:  # noqa: BLE001
        return True
