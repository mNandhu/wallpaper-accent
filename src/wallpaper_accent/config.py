"""Paths, tunable knobs, fixed palette, and component enablement.

Everything machine/user-tunable lives here. To disable a tool, drop it from
DEFAULT_COMPONENTS (or set WALLPAPER_ACCENT_COMPONENTS at runtime).
"""
from __future__ import annotations

import json
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
# Persistent knob overrides, written by `config set`. Lives in STATE_DIR (the
# XDG *config* dir is this git repo itself, so it can't hold user settings).
SETTINGS_FILE = STATE_DIR / "settings.json"
FZF_ENV = STATE_DIR / "fzf.env"
P10K_ZSH = STATE_DIR / "p10k-accent.zsh"
ZSH_SYNTAX = STATE_DIR / "zsh-syntax.zsh"
NVIM_THEME = HOME / ".config/nvim/lua/themes/wallpaper_accent.lua"
TMUX_CONF = STATE_DIR / "tmux-accent.conf"

# launchd agent identity (used by the `doctor` subcommand to check it is loaded).
AGENT_LABEL = "com.kmurthi.wallpaper-accent"
LAUNCH_AGENT_PLIST = HOME / "Library/LaunchAgents" / f"{AGENT_LABEL}.plist"

# --- Tunable knobs ----------------------------------------------------------
# Material's dark `surface` is almost neutral (chroma ~5), so an accent barely
# shows; we build the background from the accent's own hue at a dark tone with
# bounded chroma instead. The guards keep the accent distinct from the FIXED
# syntax hues (Catppuccin base08..base0F) so a same-hued wallpaper can't make
# the cursor/prompt impersonate a syntax colour.
#
# Every knob resolves with precedence: environment variable > settings file
# (SETTINGS_FILE, via `config set`) > built-in default. All are folded into the
# idempotency key (tuning_signature) so a change re-themes without --force.
SCHEMES = ("vibrant", "tonalspot", "expressive", "fruitsalad", "rainbow", "content")

# knob -> (env var, coercer, default, help). The knob name doubles as the
# settings-file key and the tuning_signature key — one registry keeps them in
# sync. Add a knob here and it is configurable everywhere.
KNOBS: dict[str, tuple] = {
    "scheme":       ("GHOSTTY_ACCENT_SCHEME",       str,   "vibrant", "accent harmony (" + ", ".join(SCHEMES) + ")"),
    "bg_tone":      ("GHOSTTY_ACCENT_BG_TONE",      float, 14.0,      "background lightness 0-100 (lower = darker)"),
    "bg_chroma":    ("GHOSTTY_ACCENT_BG_CHROMA",    float, 22.0,      "background colourfulness (lower = greyer/less tint)"),
    "black_tone":   ("GHOSTTY_ACCENT_BLACK_TONE",   float, 22.0,      "ANSI 'black' lightness"),
    "black_chroma": ("GHOSTTY_ACCENT_BLACK_CHROMA", float, 18.0,      "ANSI 'black' tint"),
    "min_hue_sep":  ("GHOSTTY_ACCENT_MIN_HUE_SEP",  float, 20.0,      "min hue deg between accent and syntax hues (0 disables)"),
    "chroma_floor": ("GHOSTTY_ACCENT_CHROMA_FLOOR", float, 12.0,      "seeds duller than this are treated as near-grey"),
    "fallback_hue": ("GHOSTTY_ACCENT_FALLBACK_HUE", float, 210.0,     "accent hue for colourless wallpapers"),
    "fg_contrast":  ("GHOSTTY_ACCENT_FG_CONTRAST",  float, 4.5,       "min WCAG contrast of foreground over background"),
}
_MISSING = object()


def load_settings() -> dict:
    """Persistent knob overrides from SETTINGS_FILE (missing/corrupt -> {})."""
    try:
        data = json.loads(SETTINGS_FILE.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def knob_value(key: str):
    """Resolve one knob's effective value: env var > settings file > default."""
    env_var, coerce, default, _ = KNOBS[key]
    raw = os.environ.get(env_var)
    if raw is None or not str(raw).strip():
        raw = load_settings().get(key, default)
    val = coerce(raw)
    return val.strip().lower() if coerce is str else val


def knob_source(key: str) -> str:
    """Where the effective value comes from: 'env' | 'file' | 'default'."""
    if os.environ.get(KNOBS[key][0], "").strip():
        return "env"
    return "file" if key in load_settings() else "default"


def set_knob(key: str, value: str):
    """Persist a knob to SETTINGS_FILE. Raises KeyError (unknown knob) or
    ValueError (bad value). Returns the coerced value stored."""
    if key not in KNOBS:
        raise KeyError(key)
    coerce = KNOBS[key][1]
    val = coerce(value)
    if coerce is str:
        val = val.strip().lower()
        if key == "scheme" and val not in SCHEMES:
            raise ValueError(f"scheme must be one of: {', '.join(SCHEMES)}")
    settings = load_settings()
    settings[key] = val
    _write_settings(settings)
    return val


def unset_knob(key: str) -> bool:
    """Remove a knob override; returns True if one was present."""
    if key not in KNOBS:
        raise KeyError(key)
    settings = load_settings()
    if settings.pop(key, _MISSING) is _MISSING:
        return False
    _write_settings(settings)
    return True


def _write_settings(settings: dict) -> None:
    from .util import atomic_write
    atomic_write(SETTINGS_FILE, json.dumps(settings, indent=2, sort_keys=True) + "\n")


# Resolved module constants (import-time; each CLI run is a fresh process, so
# `config set` in one invocation is picked up by the next `theme` run).
ACCENT_SCHEME = knob_value("scheme")
BG_TONE = knob_value("bg_tone")
BG_CHROMA_CAP = knob_value("bg_chroma")
BLACK_TONE = knob_value("black_tone")
BLACK_CHROMA_CAP = knob_value("black_chroma")
MIN_HUE_SEP = knob_value("min_hue_sep")
CHROMA_FLOOR = knob_value("chroma_floor")
FALLBACK_HUE = knob_value("fallback_hue")
FG_MIN_CONTRAST = knob_value("fg_contrast")

# Non-knob internals (not user-tunable).
MONOCHROMATIC_SCHEMES = {"tonalspot"}  # nudge the semantic hue, not the accent
GREY_HUE_CHROMA = 5.0                   # below this a seed's hue is meaningless
FG_VARIANT_MIN_CONTRAST = 3.0
REPORT_DE_THRESHOLD = 12.0              # ΔE below which collision_report flags a role
ENGINE_VERSION = 2                      # bump when the palette math changes

# Enabled components, in run order. Edit this list to disable a tool, or set
# WALLPAPER_ACCENT_COMPONENTS="ghostty,fzf" to override at runtime.
DEFAULT_COMPONENTS = ["ghostty", "fzf", "p10k", "zsh-syntax", "nvim", "tmux"]


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
