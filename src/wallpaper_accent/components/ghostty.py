"""ghostty: bg/fg, cursor, selection, neutral greys. Live reload via SIGUSR2."""
from __future__ import annotations

import signal

from .. import config
from ..procs import signal_all
from ..util import atomic_write, log


def emit(pal: dict) -> None:
    s, a = pal["surface"], pal["accent"]
    conf = f"""\
# Ghostty wallpaper-accent theme — GENERATED, do not edit by hand.
# Source: {pal["source"]}
# Appearance: {"dark" if pal["dark"] else "light"}   Seed accent: {pal["seed"]}
#
# Background is the accent hue as a tinted dark; cursor + selection use the
# accent; neutral greys track it. Semantic ANSI hues (red/green/yellow/blue/
# magenta/cyan) stay from the base config so log/diff/ls colours stay legible.

background = {s["bg"]}
foreground = {s["fg"]}

cursor-color = {a["primary"]}
cursor-text = {a["on_primary"]}

selection-background = {a["tertiary_container"]}
selection-foreground = {a["on_tertiary_container"]}

# Neutral greys, accent-tinted (no semantic-hue collision)
palette = 0={s["black"]}
palette = 8={s["outline"]}
palette = 7={s["fg_variant"]}
palette = 15={s["fg"]}
"""
    atomic_write(config.OUT_CONF, conf)


def reload() -> None:
    n = signal_all("ghostty", signal.SIGUSR2)
    log(f"ghostty: reloaded {n} process(es)" if n else "ghostty: none running")
