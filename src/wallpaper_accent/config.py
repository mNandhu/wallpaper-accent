"""Paths, tunable knobs, fixed palette, and component enablement.

Everything machine/user-tunable lives here. To disable a tool, drop it from
DEFAULT_COMPONENTS (or set WALLPAPER_ACCENT_COMPONENTS at runtime).
"""
from __future__ import annotations

import os
from pathlib import Path

HOME = Path.home()
WALLPAPER_INDEX = (
    HOME / "Library/Application Support/com.apple.wallpaper/Store/Index.plist"
)

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state")) / "wallpaper-accent"
OUT_CONF = STATE_DIR / "ghostty.conf"
STATE_FILE = STATE_DIR / "state.json"
COLORS_JSON = STATE_DIR / "colors.json"
FZF_ENV = STATE_DIR / "fzf.env"
P10K_ZSH = STATE_DIR / "p10k-accent.zsh"
ZSH_SYNTAX = STATE_DIR / "zsh-syntax.zsh"
NVIM_THEME = HOME / ".config/nvim/lua/themes/wallpaper_accent.lua"

# --- Background tint knobs (override via env) -------------------------------
# Material's dark `surface` is almost neutral (chroma ~5), so an accent barely
# shows ("black with a hint"). Instead we build the background from the accent's
# own hue at a dark tone with bounded chroma, so it reads as a genuinely tinted
# dark. Raise *_CHROMA for more colour; raise *_TONE for a lighter background.
BG_TONE = float(os.environ.get("GHOSTTY_ACCENT_BG_TONE", "14"))
BG_CHROMA_CAP = float(os.environ.get("GHOSTTY_ACCENT_BG_CHROMA", "22"))
BLACK_TONE = float(os.environ.get("GHOSTTY_ACCENT_BLACK_TONE", "22"))
BLACK_CHROMA_CAP = float(os.environ.get("GHOSTTY_ACCENT_BLACK_CHROMA", "18"))

# Accent harmony: which Material scheme derives primary/secondary/tertiary from
# the seed. "tonalspot" = monochromatic (one muted hue — looks monotonous);
# "vibrant" = distinct hues with real chroma (default); also "expressive",
# "fruitsalad", "rainbow", "content". This is the color-wheel harmony choice.
ACCENT_SCHEME = os.environ.get("GHOSTTY_ACCENT_SCHEME", "vibrant").strip().lower()

# Enabled components, in run order. Edit this list to disable a tool, or set
# WALLPAPER_ACCENT_COMPONENTS="ghostty,fzf" to override at runtime.
DEFAULT_COMPONENTS = ["ghostty", "fzf", "p10k", "zsh-syntax", "nvim"]


def enabled_component_names() -> list[str]:
    env = os.environ.get("WALLPAPER_ACCENT_COMPONENTS", "").strip()
    if env:
        return [c.strip() for c in env.split(",") if c.strip()]
    return list(DEFAULT_COMPONENTS)


# Fixed semantic hues (Catppuccin Mocha). Shared by every emitter so red stays
# red, green stays green, etc., regardless of the wallpaper accent.
CATPPUCCIN = {
    "red": "#f38ba8",
    "peach": "#fab387",
    "yellow": "#f9e2af",
    "green": "#a6e3a1",
    "teal": "#94e2d5",
    "sky": "#89dceb",
    "blue": "#89b4fa",
    "mauve": "#cba6f7",
    "flamingo": "#f2cdcd",
    "pink": "#f5c2e7",
}
