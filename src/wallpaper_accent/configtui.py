"""Interactive knob editor: an arrow-key menu that live-applies to ghostty.

`config edit` opens a menu of every tunable knob. Up/Down move the selection;
Left/Right change the selected knob's value; each change is persisted to
SETTINGS_FILE and applied live to any running ghostty — rebuild the palette from
the current wallpaper, re-emit ghostty.conf, and SIGUSR2. `u` reverts a knob to
its default, `q`/Esc quits.

Live preview is cheap because palette._quantize caches the expensive image
quantization by (path, mtime); only the knob-driven colour math re-runs per key.
"""
from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

from . import config
from .components import ghostty
from .procs import signal_all
from .util import log
from .wallpaper import find_wallpaper, is_dark_appearance

# Left/Right nudge step for numeric knobs (default 1.0).
_STEP = {"fg_contrast": 0.5}
# Clamp ranges per numeric knob: (min, max).
_BOUNDS = {
    "bg_tone": (0.0, 100.0),
    "bg_chroma": (0.0, 150.0),
    "black_tone": (0.0, 100.0),
    "black_chroma": (0.0, 150.0),
    "min_hue_sep": (0.0, 180.0),
    "chroma_floor": (0.0, 150.0),
    "fallback_hue": (0.0, 360.0),
    "fg_contrast": (1.0, 21.0),
}

CSI = "\x1b["
_ALT_ON = CSI + "?1049h"      # enter alternate screen
_ALT_OFF = CSI + "?1049l"     # leave alternate screen
_HIDE = CSI + "?25l"
_SHOW = CSI + "?25h"
_CLEAR = CSI + "2J" + CSI + "H"


_ARROWS = {b"A": "UP", b"B": "DOWN", b"C": "RIGHT", b"D": "LEFT"}


def _read_key(fd: int, _buf: bytearray) -> str:
    """Consume one logical key from the raw terminal fd, buffering any extra
    bytes in `_buf`. Fixes two things a naive `sys.stdin.read(1)` gets wrong:
    (1) arrows are a 3-byte CSI sequence (\\x1b[A..D) the terminal delivers at
    once; we parse the whole sequence rather than split it; (2) key-repeat (a
    held arrow) can deliver several sequences in a single read — we keep the
    remainder in `_buf` and return them one call at a time instead of dropping
    them. A lone \\x1b or EOF is treated as quit."""
    if not _buf:
        chunk = os.read(fd, 64)
        if not chunk:                  # EOF — treat as quit
            return "ESC"
        _buf.extend(chunk)
    if _buf[:1] != b"\x1b":            # ordinary key: one char
        return chr(_buf.pop(0))
    if _buf[:2] == b"\x1b[" and bytes(_buf[2:3]) in _ARROWS:
        code = bytes(_buf[2:3])
        del _buf[:3]
        return _ARROWS[code]
    del _buf[:1]                       # bare Esc / unhandled escape -> quit
    return "ESC"


def _adjust(key: str, direction: int) -> None:
    """Change knob `key` by one step in `direction` (-1/+1) and persist it."""
    coerce = config.KNOBS[key][1]
    if coerce is str:  # only `scheme` — cycle the allowed values
        opts = list(config.SCHEMES)
        cur = config.knob_value(key)
        idx = (opts.index(cur) + direction) % len(opts) if cur in opts else 0
        config.set_knob(key, opts[idx])
        return
    step = _STEP.get(key, 1.0)
    val = float(config.knob_value(key)) + direction * step
    lo, hi = _BOUNDS.get(key, (0.0, None))
    if lo is not None:
        val = max(lo, val)
    if hi is not None:
        val = min(hi, val)
    config.set_knob(key, str(round(val, 2)))


def _fmt_value(key: str) -> str:
    val = config.knob_value(key)
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val)


def _apply_live(image: Path | None, dark: bool) -> str:
    """Rebuild the palette and push it to ghostty. Returns a status line.
    Palette build logs to stderr; we route it into the returned string instead
    so it never corrupts the menu."""
    if image is None:
        return "no image wallpaper — saved to settings, not previewed"
    from .palette import build_palette

    try:
        pal = build_palette(image, dark)
        ghostty.emit(pal)
    except Exception as exc:  # noqa: BLE001
        return f"apply failed: {exc}"
    n = signal_all("ghostty", signal.SIGUSR2)
    where = f"reloaded {n} ghostty process(es)" if n else "no ghostty running"
    return f"applied {pal['seed']} ({'dark' if dark else 'light'}) — {where}"


def _render(rows: list[str], sel: int, image: Path | None, dark: bool, status: str) -> None:
    kw = max(len(k) for k in config.KNOBS)
    out = [_CLEAR]
    out.append(f"{CSI}1m  wallpaper-accent · live config edit{CSI}0m\n")
    src = str(image) if image else "(no image wallpaper)"
    out.append(f"  wallpaper: {src}   appearance: {'dark' if dark else 'light'}\n")
    out.append(f"  settings:  {config.SETTINGS_FILE}\n\n")
    for i, key in enumerate(rows):
        marker = "›" if i == sel else " "
        val = _fmt_value(key)
        source = config.knob_source(key)
        help_ = config.KNOBS[key][3]
        line = f"  {marker} {key.ljust(kw)}  {val:>7}  [{source:7}]  {help_}"
        out.append((f"{CSI}7m{line}{CSI}0m" if i == sel else line) + "\n")
    out.append(
        f"\n  {CSI}2m↑/↓ select   ←/→ change   u reset   q quit{CSI}0m\n"
    )
    out.append(f"\n  {status}\n")
    sys.stdout.write("".join(out).replace("\n", "\r\n"))
    sys.stdout.flush()


def _prompt_yes(prompt: str) -> bool:
    """Y/n prompt in cooked mode; empty answer (Enter) defaults to yes."""
    try:
        ans = input(prompt).strip().lower()
    except EOFError:
        return False
    return ans in ("", "y", "yes")


def run() -> int:
    """Entry point for `config edit`."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        log("config edit needs an interactive terminal (stdin/stdout must be a tty)")
        return 1
    try:
        import termios
        import tty
    except ImportError:  # pragma: no cover - non-POSIX
        log("config edit is only supported on POSIX terminals")
        return 1

    rows = list(config.KNOBS)
    sel = 0
    dark = is_dark_appearance()
    image = find_wallpaper()
    status = "ready — arrows to edit; ghostty updates live"

    fd = sys.stdin.fileno()
    keybuf = bytearray()
    changed = False
    old = termios.tcgetattr(fd)
    sys.stdout.write(_ALT_ON + _HIDE)
    try:
        tty.setraw(fd)
        while True:
            _render(rows, sel, image, dark, status)
            key = _read_key(fd, keybuf)
            if key in ("q", "Q", "ESC", "\x03", "\x04"):  # q / Esc / ^C / ^D
                break
            if key in ("UP", "k"):
                sel = (sel - 1) % len(rows)
            elif key in ("DOWN", "j"):
                sel = (sel + 1) % len(rows)
            elif key in ("LEFT", "h", "RIGHT", "l"):
                _adjust(rows[sel], -1 if key in ("LEFT", "h") else 1)
                config.refresh()
                status = _apply_live(image, dark)
                changed = True
            elif key in ("u", "U"):
                config.unset_knob(rows[sel])
                config.refresh()
                status = _apply_live(image, dark) + "  (reset to default)"
                changed = True
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        sys.stdout.write(_SHOW + _ALT_OFF)
        sys.stdout.flush()

    print(f"saved to {config.SETTINGS_FILE}")
    if changed and _prompt_yes("Apply theme to all components now? [Y/n] "):
        import argparse

        from .cli import _theme
        return _theme(argparse.Namespace(
            show=False, undo=False, image=None, dark=dark, light=not dark,
            force=True, no_reload=False, only=None, skip=None, to_stdout=False,
        ))
    print("all components pick up these knobs on the next `theme` run "
          "(ghostty was already live-updated).")
    return 0
