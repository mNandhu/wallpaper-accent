"""Component registry — one entry per themed tool.

A Component bundles an `emit(pal)` (writes its config fragment) and an optional
`reload()` (applies it to running instances). To ADD a tool: create a module
here with `emit` (+ optional `reload`), register it below, and add its name to
config.DEFAULT_COMPONENTS. To DISABLE a tool: remove its name from
config.DEFAULT_COMPONENTS (or set WALLPAPER_ACCENT_COMPONENTS at runtime).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .. import config
from ..util import log
from . import fzf, ghostty, nvim, p10k, tmux, zsh_syntax


@dataclass(frozen=True)
class Component:
    name: str
    emit: Callable[[dict], None]
    reload: Optional[Callable[[], None]] = None


REGISTRY: dict[str, Component] = {
    "ghostty": Component("ghostty", ghostty.emit, ghostty.reload),
    "fzf": Component("fzf", fzf.emit),
    "p10k": Component("p10k", p10k.emit),
    "zsh-syntax": Component("zsh-syntax", zsh_syntax.emit),
    "nvim": Component("nvim", nvim.emit, nvim.reload),
    "tmux": Component("tmux", tmux.emit, tmux.reload),
}


def enabled() -> list[Component]:
    """Enabled components in run order (unknown names are skipped with a warning)."""
    out: list[Component] = []
    for name in config.enabled_component_names():
        comp = REGISTRY.get(name)
        if comp is None:
            log(f"unknown component '{name}' (known: {', '.join(REGISTRY)})")
            continue
        out.append(comp)
    return out
