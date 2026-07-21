"""Palette history: `theme --undo` restores the previously-applied palette.

Two files under STATE_DIR track this, both storing the *full* `pal` dict
(colors.json only mirrors a trimmed subset — see cli._COLORS_KEYS — so it
can't be replayed through `Component.emit`):

  LAST_PALETTE_FILE  the full palette currently applied (superset of colors.json)
  HISTORY_FILE       a ring of past palettes, oldest first, capped at HISTORY_MAX

`advance(pal)` is called on every real theme change: it pushes the outgoing
"current" onto the ring, then makes `pal` current. `undo()` pops the ring's
most recent entry and makes *that* current, WITHOUT pushing the palette it
replaces — so repeated `--undo` walks straight back through history instead
of oscillating between the last two themes.
"""
from __future__ import annotations

import json

from . import config
from .util import atomic_write


def _same(a: dict, b: dict) -> bool:
    return (a.get("seed"), a.get("scheme"), a.get("dark")) == (b.get("seed"), b.get("scheme"), b.get("dark"))


def _load(path) -> object:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _load_ring() -> list[dict]:
    data = _load(config.HISTORY_FILE)
    return data if isinstance(data, list) else []


def current() -> dict | None:
    """The full palette currently applied, or None if nothing has been themed yet."""
    data = _load(config.LAST_PALETTE_FILE)
    return data if isinstance(data, dict) else None


def advance(pal: dict) -> None:
    """Record a real theme change: push the outgoing current palette onto the
    history ring (skipped if it's the same accent — e.g. a `--force` re-run),
    then make `pal` the new current."""
    prev = current()
    if prev is not None and not _same(prev, pal):
        ring = _load_ring()
        ring.append(prev)
        ring = ring[-config.HISTORY_MAX:]
        atomic_write(config.HISTORY_FILE, json.dumps(ring))
    atomic_write(config.LAST_PALETTE_FILE, json.dumps(pal))


def undo() -> dict | None:
    """Pop the most recent past palette and make it current. Returns None
    (and leaves state untouched) if there's nothing to undo to."""
    ring = _load_ring()
    if not ring:
        return None
    pal = ring.pop()
    atomic_write(config.HISTORY_FILE, json.dumps(ring))
    atomic_write(config.LAST_PALETTE_FILE, json.dumps(pal))
    return pal
