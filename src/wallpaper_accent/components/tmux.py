"""tmux: status bar, pane borders, copy-mode selection. Live reload via CLI.

Accent drives status bar / active pane border / window-status-current / clock;
`surface["selection"]`/`["on_selection"]` (the single selection source, shared
with every other tool) drives copy-mode. Message/command text stays on neutral
surfaces so tmux prompts remain legible on any wallpaper. Reload class 2 (live
via CLI): `tmux source-file` repaints running servers.
"""
from __future__ import annotations

import shutil
import subprocess

from .. import config
from ..util import atomic_write, log


def emit(pal: dict) -> None:
    s, a = pal["surface"], pal["accent"]
    conf = f"""\
# Tmux wallpaper-accent theme — GENERATED, do not edit by hand.
# Source: {pal["source"]}
# Appearance: {"dark" if pal["dark"] else "light"}   Seed accent: {pal["seed"]}
#
# Accent tints the status bar, active pane border, current window and clock;
# copy-mode uses the shared selection colour. Message/command text stays on
# neutral surfaces so prompts remain legible under any wallpaper.

set -g status-style "bg={s['bg']},fg={s['fg_variant']}"
set -g status-left-style "fg={s['fg']}"
set -g status-right-style "fg={s['fg_variant']}"

set -g window-status-current-style "fg={a['on_primary']},bg={a['primary']},bold"
set -g window-status-style "fg={s['fg_variant']}"
set -g window-status-activity-style "fg={a['secondary']}"

set -g pane-border-style "fg={s['outline']}"
set -g pane-active-border-style "fg={a['primary']}"
set -g display-panes-active-colour "{a['primary']}"
set -g display-panes-colour "{s['outline']}"

set -g mode-style "bg={s['selection']},fg={s['on_selection']}"
set -g message-style "bg={s['black']},fg={s['fg']}"
set -g message-command-style "bg={s['black']},fg={s['fg']}"
set -g clock-mode-colour "{a['secondary']}"
"""
    atomic_write(config.TMUX_CONF, conf)


def reload() -> None:
    tmux = shutil.which("tmux")
    if not tmux:
        log("tmux: not installed")
        return
    # No running server → nothing to repaint; the fragment is sourced on start.
    if subprocess.run([tmux, "ls"], capture_output=True).returncode != 0:
        log("tmux: no server running")
        return
    r = subprocess.run(
        [tmux, "source-file", str(config.TMUX_CONF)], capture_output=True, text=True
    )
    if r.returncode == 0:
        log("tmux: reloaded")
    else:
        log(f"tmux: source-file failed: {r.stderr.strip()}")
