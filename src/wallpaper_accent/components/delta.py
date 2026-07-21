"""delta (git pager): accent on file/hunk headers + the line-number gutter.

Diff +/- keep delta's fixed red/green fills (`syntax auto`) so additions and
deletions read correctly on any wallpaper; the accent only tints the file and
hunk-header decorations and the line-number gutter frame, and the fixed base16
semantic hues drive the +/- line-number markers. git/delta re-read config each
invocation (reload class 3), so writing the fragment is enough — no reload.
"""
from __future__ import annotations

from .. import config
from ..util import atomic_write


def emit(pal: dict) -> None:
    s, a, b = pal["surface"], pal["accent"], pal["base16"]
    conf = f"""\
# Delta wallpaper-accent theme — GENERATED, do not edit by hand.
# Source: {pal["source"]}
# Appearance: {"dark" if pal["dark"] else "light"}   Seed accent: {pal["seed"]}
#
# Include this from ~/.gitconfig: [include] path = .../delta.gitconfig
# +/- keep delta's fixed red/green fills; the accent only tints the file and
# hunk-header decorations and the line-number gutter, and the fixed base16
# semantic hues drive the +/- markers, so diffs stay legible under any wallpaper.
[delta]
    line-numbers = true
    file-style = "{a['primary']}" bold
    file-decoration-style = "{a['primary']}" ul
    hunk-header-style = syntax
    hunk-header-decoration-style = "{a['secondary']}" ul
    hunk-header-line-number-style = "{a['secondary']}"
    line-numbers-left-style = "{s['outline']}"
    line-numbers-right-style = "{s['outline']}"
    line-numbers-zero-style = "{b['base03']}"
    line-numbers-minus-style = "{b['base08']}"
    line-numbers-plus-style = "{b['base0B']}"
    minus-style = syntax auto
    minus-emph-style = syntax auto
    plus-style = syntax auto
    plus-emph-style = syntax auto
"""
    atomic_write(config.DELTA_GITCONFIG, conf)
