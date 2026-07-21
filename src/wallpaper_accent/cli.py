"""CLI + orchestration: wallpaper -> palette -> enabled components -> reloads.

Subcommands: `theme` (default), `show`, `doctor`, `components`, `preview`. For
backward compatibility a bare flag invocation (e.g. `wallpaper-accent --force`,
as the launchd agent runs) is treated as `theme --force`, so no launchd/shebang
caller needs updating.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import components, config
from .palette import build_palette, collision_report
from .show import show_palette
from .util import atomic_write, log
from .wallpaper import find_wallpaper, is_dark_appearance

_COLORS_KEYS = ("source", "seed", "scheme", "dark", "accent", "surface", "base16")
SUBCOMMANDS = {"theme", "show", "doctor", "components", "preview", "config"}


def _colors_subset(pal: dict) -> str:
    return json.dumps({k: pal[k] for k in _COLORS_KEYS}, indent=2)


def _write_colors_json(pal: dict) -> None:
    atomic_write(config.COLORS_JSON, _colors_subset(pal))


def _theme(args: argparse.Namespace) -> int:
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
    if args.only:
        want = set(args.only)
        comps = [c for c in comps if c.name in want]
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


def _components() -> int:
    enabled = set(config.enabled_component_names())
    print("components (name — enabled? — reload class):")
    for name, comp in components.REGISTRY.items():
        mark = "on " if name in enabled else "off"
        kind = "live-reload" if comp.reload else "new-process"
        print(f"  [{mark}] {name:15} {kind}")
    return 0


def _preview(image_arg: str) -> int:
    image = Path(image_arg).expanduser()
    if not image.is_file():
        log(f"no such image: {image}")
        return 1
    pal = build_palette(image, is_dark_appearance())
    print(_colors_subset(pal))
    for line in collision_report(pal):
        log(f"collision: {line}")
    return 0


def _config(args: argparse.Namespace) -> int:
    action = args.config_action
    known = ", ".join(config.KNOBS)
    if action in ("get", "set", "unset"):
        if not args.key:
            log(f"'config {action}' needs a knob name. known: {known}")
            return 1
        if args.key not in config.KNOBS:
            log(f"unknown knob '{args.key}'. known: {known}")
            return 1

    if action == "get":
        print(config.knob_value(args.key))
        return 0
    if action == "set":
        if args.value is None:
            log("usage: config set KEY VALUE")
            return 1
        try:
            val = config.set_knob(args.key, args.value)
        except ValueError as exc:
            log(str(exc))
            return 1
        print(f"{args.key} = {val}  →  {config.SETTINGS_FILE}")
        print("apply now: wallpaper-accent theme --force "
              "(otherwise it applies on the next wallpaper change)")
        return 0
    if action == "unset":
        removed = config.unset_knob(args.key)
        print(f"{args.key}: {'reverted to default' if removed else 'was not set'}")
        return 0
    if action == "edit":
        from .configtui import run as run_editor
        return run_editor()

    # list (default)
    print(f"\n  wallpaper-accent knobs  (settings: {config.SETTINGS_FILE})\n")
    kw = max(len(k) for k in config.KNOBS)
    for key, (_env, _c, _default, help_) in config.KNOBS.items():
        val = str(config.knob_value(key))
        src = config.knob_source(key)
        print(f"  {key.ljust(kw)}  {val:9} [{src:7}]  {help_}")
    print("\n  config edit                 interactive menu (arrow keys, live ghostty)")
    print("  config set <knob> <value>   persist an override")
    print("  config unset <knob>         revert to default")
    print("  precedence: env var > settings file > default\n")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="wallpaper-accent",
        description="Theme terminal tools from the macOS wallpaper's accent color.",
    )
    sub = ap.add_subparsers(dest="cmd")

    t = sub.add_parser("theme", help="re-theme from the current wallpaper (default)")
    t.add_argument("--force", action="store_true",
                   help="regenerate even if the wallpaper is unchanged")
    t.add_argument("--no-reload", action="store_true",
                   help="write fragments but do not signal apps")
    t.add_argument("--print", dest="to_stdout", action="store_true",
                   help="print the resolved palette (colors.json) and exit")
    t.add_argument("--show", action="store_true",
                   help="print the current palette as color swatches and exit")
    t.add_argument("--image", metavar="PATH",
                   help="use this image instead of the current wallpaper")
    t.add_argument("--only", metavar="NAME", action="append",
                   help="theme only this component (repeatable)")
    appearance = t.add_mutually_exclusive_group()
    appearance.add_argument("--dark", action="store_true")
    appearance.add_argument("--light", action="store_true")

    sub.add_parser("show", help="print the current palette as color swatches")
    sub.add_parser("doctor", help="check prerequisites and integration points")
    sub.add_parser("components", help="list known and enabled components")
    p = sub.add_parser("preview",
                        help="build a palette from an image and print JSON (writes nothing)")
    p.add_argument("image", metavar="PATH")
    c = sub.add_parser("config",
                       help="get/set persistent palette knobs (no env vars needed)")
    c.add_argument("config_action", nargs="?", default="list",
                   choices=["list", "get", "set", "unset", "edit"],
                   help="list (default), get, set, unset, or edit (interactive) a knob")
    c.add_argument("key", nargs="?", help="knob name (see `config list`)")
    c.add_argument("value", nargs="?", help="new value (for `config set`)")
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Backward compat: a bare flag invocation means the default `theme` command.
    if not argv:
        argv = ["theme"]
    elif argv[0] not in SUBCOMMANDS and argv[0] not in ("-h", "--help"):
        argv = ["theme", *argv]

    args = _build_parser().parse_args(argv)
    cmd = args.cmd or "theme"
    if cmd == "show":
        return show_palette()
    if cmd == "doctor":
        from .doctor import run
        return run()
    if cmd == "components":
        return _components()
    if cmd == "preview":
        return _preview(args.image)
    if cmd == "config":
        return _config(args)
    return _theme(args)
