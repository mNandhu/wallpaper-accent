"""lazygit: accent on active border / selected line / cherry-picked commits.

Accent drives the active window border, options text and the selected-line
background (via the shared `surface["selection"]`); the fixed base16 red marks
unstaged changes so status stays semantic. lazygit re-reads its config each
launch (reload class 3), merged in via LG_CONFIG_FILE — writing the fragment is
enough, no reload.
"""
from __future__ import annotations

from .. import config
from ..util import atomic_write


def emit(pal: dict) -> None:
    s, a, b = pal["surface"], pal["accent"], pal["base16"]
    conf = f"""\
# Lazygit wallpaper-accent theme — GENERATED, do not edit by hand.
# Source: {pal["source"]}
# Appearance: {"dark" if pal["dark"] else "light"}   Seed accent: {pal["seed"]}
#
# Merge via LG_CONFIG_FILE (comma-separated, this file last so it wins):
#   export LG_CONFIG_FILE="$HOME/.config/lazygit/config.yml,{config.LAZYGIT_YML}"
# Accent tints active border / options / selected line; base16 red keeps
# unstaged changes semantic so the status column stays legible on any wallpaper.
gui:
  theme:
    activeBorderColor:
      - "{a['primary']}"
      - bold
    inactiveBorderColor:
      - "{s['outline']}"
    searchingActiveBorderColor:
      - "{a['secondary']}"
      - bold
    optionsTextColor:
      - "{a['secondary']}"
    selectedLineBgColor:
      - "{s['selection']}"
    cherryPickedCommitBgColor:
      - "{s['selection']}"
    cherryPickedCommitFgColor:
      - "{s['on_selection']}"
    markedBaseCommitBgColor:
      - "{a['tertiary_container']}"
    markedBaseCommitFgColor:
      - "{a['on_tertiary_container']}"
    unstagedChangesColor:
      - "{b['base08']}"
    defaultFgColor:
      - "{s['fg']}"
"""
    atomic_write(config.LAZYGIT_YML, conf)
