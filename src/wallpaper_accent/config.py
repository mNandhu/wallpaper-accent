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

# --- Accent/semantic de-confliction guards (override via env) ---------------
# The accent is meant to look distinct from the FIXED syntax hues (Catppuccin
# base08..base0F). On a wallpaper whose dominant hue *is* one of those hues
# (e.g. a blue wallpaper vs syntax blue) the accent would otherwise impersonate
# a syntax colour. These guards keep them apart. See palette.deconflict().
#
# MIN_HUE_SEP: minimum colour-wheel separation (degrees) enforced between every
#   accent role and every fixed semantic hue. Spread schemes rotate the accent
#   away; monochromatic schemes (tonalspot) instead nudge the colliding syntax
#   hue (preserving the single-hue accent aesthetic). 0 disables the guard.
MIN_HUE_SEP = float(os.environ.get("GHOSTTY_ACCENT_MIN_HUE_SEP", "20"))
# Schemes treated as monochromatic (nudge the semantic hue, not the accent).
MONOCHROMATIC_SCHEMES = {"tonalspot"}
# CHROMA_FLOOR: seeds below this are near-greyscale → the wallpaper hue is dull
#   or (near 0) meaningless. The accent seed's chroma is lifted to the floor;
#   below GREY_HUE_CHROMA the hue is unreliable so FALLBACK_HUE is used instead.
CHROMA_FLOOR = float(os.environ.get("GHOSTTY_ACCENT_CHROMA_FLOOR", "12"))
GREY_HUE_CHROMA = 5.0
# 210 sits in the wide teal->blue gap of the fixed hue wheel, so the synthesized
# accent for a colourless wallpaper stays clear of every syntax hue.
FALLBACK_HUE = float(os.environ.get("GHOSTTY_ACCENT_FALLBACK_HUE", "210"))
# Minimum WCAG contrast of foreground text against the tinted background. Our
# background overrides Material's surface, so Material's onSurface is not
# guaranteed legible against it; enforce_contrast() lifts the tone until it is.
FG_MIN_CONTRAST = float(os.environ.get("GHOSTTY_ACCENT_FG_CONTRAST", "4.5"))
FG_VARIANT_MIN_CONTRAST = 3.0
# ΔE below which the collision report flags an accent role as confusable with a
# fixed syntax hue (diagnostic only; --show / --print).
REPORT_DE_THRESHOLD = 12.0
# Bump when the palette math changes so a stale colors.json is regenerated.
ENGINE_VERSION = 2

# Enabled components, in run order. Edit this list to disable a tool, or set
# WALLPAPER_ACCENT_COMPONENTS="ghostty,fzf" to override at runtime.
DEFAULT_COMPONENTS = ["ghostty", "fzf", "p10k", "zsh-syntax", "nvim"]


def enabled_component_names() -> list[str]:
    env = os.environ.get("WALLPAPER_ACCENT_COMPONENTS", "").strip()
    if env:
        return [c.strip() for c in env.split(",") if c.strip()]
    return list(DEFAULT_COMPONENTS)


def tuning_signature() -> dict:
    """Palette-affecting knobs folded into the idempotency key, so changing a
    scheme/tint/guard env var re-themes without --force (colors.json otherwise
    looks up-to-date because the wallpaper is unchanged)."""
    return {
        "engine": ENGINE_VERSION,
        "scheme": ACCENT_SCHEME,
        "bg_tone": BG_TONE, "bg_chroma": BG_CHROMA_CAP,
        "black_tone": BLACK_TONE, "black_chroma": BLACK_CHROMA_CAP,
        "min_hue_sep": MIN_HUE_SEP, "chroma_floor": CHROMA_FLOOR,
        "fallback_hue": FALLBACK_HUE, "fg_contrast": FG_MIN_CONTRAST,
        "components": enabled_component_names(),
    }


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
