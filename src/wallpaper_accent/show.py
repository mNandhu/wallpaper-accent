"""`--show`: render the current palette as truecolor swatches in the terminal."""
from __future__ import annotations

import json

from .config import COLORS_JSON
from .util import log, rgb


def _swatch(hex6: str, label: str) -> str:
    r, g, b = rgb(hex6)
    fg = "0;0;0" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "255;255;255"
    return f"\x1b[48;2;{r};{g};{b}m\x1b[38;2;{fg}m  {hex6}  \x1b[0m  {label}"


def show_palette() -> int:
    if not COLORS_JSON.is_file():
        log("no palette yet — run: wallpaper-accent.py --force")
        return 1
    d = json.loads(COLORS_JSON.read_text())
    print(f"\n  wallpaper-accent  seed {d['seed']}  "
          f"scheme {d.get('scheme', '?')}  {'dark' if d['dark'] else 'light'}")
    print(f"  source: {d.get('source', '?')}\n")

    def section(title: str, items: list[tuple[str, str]]) -> None:
        print(f"  \x1b[1m{title}\x1b[0m")
        for label, hexv in items:
            print("   " + _swatch(hexv, label))
        print()

    a, s, b16 = d["accent"], d["surface"], d["base16"]
    section("accent", [(k, a[k]) for k in
            ("primary", "secondary", "tertiary", "error") if k in a])
    section("surface", [(k, s[k]) for k in
            ("bg", "black", "fg", "fg_variant", "outline", "selection") if k in s])
    section("base16", [(k, b16[k]) for k in sorted(b16)])
    return 0
