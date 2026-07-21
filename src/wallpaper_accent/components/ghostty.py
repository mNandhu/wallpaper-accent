"""ghostty: bg/fg, cursor, selection, neutral greys. Live reload via SIGUSR2."""
from __future__ import annotations

import signal

from .. import config
from ..procs import signal_all
from ..util import atomic_write, log


def emit(pal: dict) -> None:
    s, a, b = pal["surface"], pal["accent"], pal["base16"]
    conf = f"""\
# Ghostty wallpaper-accent theme — GENERATED, do not edit by hand.
# Source: {pal["source"]}
# Appearance: {"dark" if pal["dark"] else "light"}   Seed accent: {pal["seed"]}
#
# Background is the accent hue as a tinted dark; cursor + selection use the
# accent; neutral greys track it. The 6 semantic ANSI hues (red/green/yellow/
# blue/magenta/cyan) are the FIXED Catppuccin base16 hues, never the accent, so
# ls/git/diff stay legible and varied on any wallpaper (not a green monochrome).

background = {s["bg"]}
foreground = {s["fg"]}

cursor-color = {a["primary"]}
cursor-text = {a["on_primary"]}

selection-background = {s["selection"]}
selection-foreground = {s["on_selection"]}

# Neutrals: accent-tinted greys (no semantic-hue collision).
palette = 0={s["black"]}
palette = 8={s["outline"]}
palette = 7={s["fg_variant"]}
palette = 15={s["fg"]}
# Semantic ANSI, fixed Catppuccin base16 (bright 9-14 mirror normal 1-6).
palette = 1={b["base08"]}
palette = 2={b["base0B"]}
palette = 3={b["base0A"]}
palette = 4={b["base0D"]}
palette = 5={b["base0E"]}
palette = 6={b["base0C"]}
palette = 9={b["base08"]}
palette = 10={b["base0B"]}
palette = 11={b["base0A"]}
palette = 12={b["base0D"]}
palette = 13={b["base0E"]}
palette = 14={b["base0C"]}
"""
    atomic_write(config.OUT_CONF, conf)


def reload() -> None:
    n = signal_all("ghostty", signal.SIGUSR2)
    log(f"ghostty: reloaded {n} process(es)" if n else "ghostty: none running")
