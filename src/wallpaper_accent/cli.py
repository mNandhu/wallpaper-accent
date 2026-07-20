"""CLI + orchestration: wallpaper -> palette -> enabled components -> reloads."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import components, config
from .palette import build_palette, collision_report
from .show import show_palette
from .util import atomic_write, log
from .wallpaper import find_wallpaper, is_dark_appearance

_COLORS_KEYS = ("source", "seed", "scheme", "dark", "accent", "surface", "base16")


def _write_colors_json(pal: dict) -> None:
    atomic_write(config.COLORS_JSON, json.dumps({k: pal[k] for k in _COLORS_KEYS}, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="wallpaper-accent",
        description="Theme terminal tools from the macOS wallpaper's accent color.",
    )
    ap.add_argument("--force", action="store_true",
                    help="regenerate even if the wallpaper is unchanged")
    ap.add_argument("--no-reload", action="store_true",
                    help="write fragments but do not signal apps")
    ap.add_argument("--print", dest="to_stdout", action="store_true",
                    help="print the resolved palette (colors.json) and exit")
    ap.add_argument("--show", action="store_true",
                    help="print the current palette as color swatches and exit")
    ap.add_argument("--image", metavar="PATH",
                    help="use this image instead of the current wallpaper")
    appearance = ap.add_mutually_exclusive_group()
    appearance.add_argument("--dark", action="store_true")
    appearance.add_argument("--light", action="store_true")
    args = ap.parse_args()

    if args.show:
        return show_palette()

    image = Path(args.image).expanduser() if args.image else find_wallpaper()
    if image is None:
        log("wallpaper is not an image (dynamic/aerial/colour); keeping previous theme")
        return 0
    if not image.is_file():
        log(f"wallpaper path does not exist: {image}; keeping previous theme")
        return 0
    dark = True if args.dark else False if args.light else is_dark_appearance()

    key = {"image": str(image), "mtime": image.stat().st_mtime, "dark": dark,
           "tuning": config.tuning_signature()}
    if not args.force and not args.to_stdout and config.COLORS_JSON.is_file():
        try:
            prev = json.loads(config.STATE_FILE.read_text())
        except Exception:  # noqa: BLE001
            prev = None
        if prev == key:
            log("wallpaper/appearance unchanged; nothing to do")
            return 0

    pal = build_palette(image, dark)
    for line in collision_report(pal):
        log(f"collision: {line}")

    if args.to_stdout:
        _write_colors_json(pal)
        print(config.COLORS_JSON.read_text())
        return 0

    _write_colors_json(pal)
    comps = components.enabled()
    for comp in comps:
        comp.emit(pal)
    atomic_write(config.STATE_FILE, json.dumps(key, indent=2))
    log(f"themed from {image.name} (accent {pal['seed']}, "
        f"{'dark' if dark else 'light'}) [{', '.join(c.name for c in comps)}]")

    if not args.no_reload:
        for comp in comps:
            if comp.reload:
                comp.reload()
        static = [c.name for c in comps if not c.reload]
        if static:
            log(f"{', '.join(static)}: new shells will pick up the accent")
    return 0
