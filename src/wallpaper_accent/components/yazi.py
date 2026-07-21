"""yazi: a generated flavor — accent on cwd/cursor/selection/tabs, semantic fixed.

Written as a yazi *flavor* (`~/.config/yazi/flavors/wallpaper-accent.yazi/`), the
modern equivalent of the nvim generated-theme file: the user's `theme.toml` only
points at it (`[flavor] dark/light = "wallpaper-accent"`) and can still override.
Accent drives cwd, the mode indicator, tabs, the position indicator and file
markers/selection (via the shared `surface["selection"]`); the status permission
column keeps the fixed base16 semantic hues so it reads the same on any wallpaper.
yazi loads the flavor fresh each launch (reload class 3) — no live reload.
"""
from __future__ import annotations

from .. import config
from ..util import atomic_write


def emit(pal: dict) -> None:
    s, a, b = pal["surface"], pal["accent"], pal["base16"]
    conf = f"""\
# Yazi wallpaper-accent flavor — GENERATED, do not edit by hand.
# Source: {pal["source"]}
# Appearance: {"dark" if pal["dark"] else "light"}   Seed accent: {pal["seed"]}
#
# Point ~/.config/yazi/theme.toml at it: [flavor] dark = "wallpaper-accent".
# Accent tints cwd / mode / tabs / indicator / markers + the shared selection;
# the status permission column keeps the fixed base16 semantic hues.

[mgr]
cwd            = {{ fg = "{a['primary']}", bold = true }}
find_keyword   = {{ fg = "{a['tertiary']}", bold = true }}
find_position  = {{ fg = "{a['tertiary']}" }}
symlink_target = {{ fg = "{s['fg_variant']}", italic = true }}
marker_copied   = {{ fg = "{b['base0B']}", bg = "{b['base0B']}" }}
marker_cut      = {{ fg = "{b['base08']}", bg = "{b['base08']}" }}
marker_marked   = {{ fg = "{a['secondary']}", bg = "{a['secondary']}" }}
marker_selected = {{ fg = "{a['primary']}", bg = "{a['primary']}" }}
count_copied   = {{ fg = "{b['base00']}", bg = "{b['base0B']}" }}
count_cut      = {{ fg = "{b['base00']}", bg = "{b['base08']}" }}
count_selected = {{ fg = "{a['on_primary']}", bg = "{a['primary']}" }}
border_style   = {{ fg = "{s['outline']}" }}

[mode]
normal_main = {{ fg = "{a['on_primary']}", bg = "{a['primary']}", bold = true }}
normal_alt  = {{ fg = "{a['primary']}", bg = "{s['black']}" }}
select_main = {{ fg = "{s['on_selection']}", bg = "{s['selection']}", bold = true }}
select_alt  = {{ fg = "{a['tertiary']}", bg = "{s['black']}" }}
unset_main  = {{ fg = "{a['on_secondary']}", bg = "{a['secondary']}", bold = true }}
unset_alt   = {{ fg = "{a['secondary']}", bg = "{s['black']}" }}

[tabs]
active   = {{ fg = "{a['on_primary']}", bg = "{a['primary']}", bold = true }}
inactive = {{ fg = "{s['fg_variant']}", bg = "{s['black']}" }}

[indicator]
parent  = {{ fg = "{s['fg_variant']}" }}
current = {{ fg = "{a['primary']}", bold = true }}
preview = {{ fg = "{a['tertiary']}" }}

[status]
overall         = {{ fg = "{s['fg_variant']}", bg = "{s['black']}" }}
perm_type       = {{ fg = "{b['base0D']}" }}
perm_read       = {{ fg = "{b['base0A']}" }}
perm_write      = {{ fg = "{b['base08']}" }}
perm_exec       = {{ fg = "{b['base0B']}" }}
perm_sep        = {{ fg = "{b['base03']}" }}
progress_label  = {{ fg = "{s['fg']}", bold = true }}
progress_normal = {{ fg = "{a['primary']}", bg = "{s['black']}" }}
progress_error  = {{ fg = "{b['base08']}", bg = "{s['black']}" }}

[which]
cols            = 3
mask            = {{ bg = "{s['black']}" }}
cand            = {{ fg = "{a['tertiary']}" }}
rest            = {{ fg = "{s['fg_variant']}" }}
desc            = {{ fg = "{s['fg']}" }}
separator       = "  "
separator_style = {{ fg = "{s['outline']}" }}

[confirm]
border  = {{ fg = "{a['primary']}" }}
title   = {{ fg = "{a['primary']}", bold = true }}
body    = {{ fg = "{s['fg']}" }}
list    = {{ fg = "{s['fg']}" }}
btn_yes = {{ fg = "{a['on_primary']}", bg = "{a['primary']}" }}
btn_no  = {{ fg = "{s['fg']}" }}
"""
    atomic_write(config.YAZI_FLAVOR, conf)
