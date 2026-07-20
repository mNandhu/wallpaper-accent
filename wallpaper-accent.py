#!/usr/bin/env -S uv run --system-certs --no-project --script
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = ["materialyoucolor>=3.0.2"]
# ///
"""Theme terminal tools from the macOS desktop wallpaper's accent color.

A single "core" derives a Material You palette from the current wallpaper's seed
(accent) color, writes it to `colors.json`, then per-app "emitters" render config
fragments for each tool and reload hooks apply them live:

    ghostty   -> wallpaper-accent.conf        (SIGUSR2 reload)
    fzf       -> theme/fzf.env                 (new shells)
    p10k      -> theme/p10k-accent.zsh         (new shells)
    nvim      -> nvim/lua/themes/wallpaper_accent.lua (SIGUSR1 / headless recompile)

Design rule shared across every tool: the accent drives surfaces, cursor,
selection and neutral greys; the semantic hues (red/green/yellow/blue/magenta/
cyan and code syntax) stay on a fixed, legible palette so logs, diffs and syntax
highlighting never become unreadable under an odd wallpaper.

Run via uv (deps auto-provisioned):

    uv run --system-certs --no-project --script wallpaper-accent.py [--force]
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import signal
import subprocess
import sys
import tempfile
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


def log(msg: str) -> None:
    print(f"[wallpaper-accent] {msg}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# macOS glue: wallpaper + appearance
# --------------------------------------------------------------------------- #
def find_wallpaper() -> Path | None:
    """Return the current wallpaper image path, or None if it is not an image.

    Primary source is the wallpaper store's Index.plist (no TCC prompt, works
    under launchd); falls back to AppleScript. Dynamic/aerial/solid-colour
    wallpapers have no backing image file and yield None.
    """
    return _wallpaper_from_index() or _wallpaper_from_osascript()


def _wallpaper_from_index() -> Path | None:
    if not WALLPAPER_INDEX.is_file():
        return None
    try:
        xml = subprocess.check_output(
            ["plutil", "-convert", "xml1", "-o", "-", str(WALLPAPER_INDEX)]
        )
        root = plistlib.loads(xml)
    except Exception as exc:  # noqa: BLE001 - fall back below
        log(f"index parse failed: {exc}")
        return None

    found: list[Path] = []

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)
        elif isinstance(obj, bytes) and obj[:6] == b"bplist":
            try:
                inner = plistlib.loads(obj)
            except Exception:  # noqa: BLE001
                return
            if isinstance(inner, dict) and inner.get("type") == "imageFile":
                url = inner.get("url", {})
                rel = url.get("relative") if isinstance(url, dict) else None
                if isinstance(rel, str) and rel.startswith("file://"):
                    from urllib.parse import unquote, urlparse

                    found.append(Path(unquote(urlparse(rel).path)))

    walk(root)
    return found[0] if found else None


def _wallpaper_from_osascript() -> Path | None:
    try:
        out = subprocess.check_output(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get picture of current desktop',
            ],
            text=True,
        ).strip()
    except Exception as exc:  # noqa: BLE001
        log(f"osascript fallback failed: {exc}")
        return None
    if not out or out == "missing value":
        return None
    return Path(out.split(",")[0].strip())


def is_dark_appearance() -> bool:
    try:
        out = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True,
            text=True,
        )
        return out.returncode == 0 and out.stdout.strip() == "Dark"
    except Exception:  # noqa: BLE001
        return True


# --------------------------------------------------------------------------- #
# Core: wallpaper -> full palette
# --------------------------------------------------------------------------- #
def build_palette(image: Path, dark: bool) -> dict:
    from materialyoucolor.quantize import ImageQuantizeCelebi
    from materialyoucolor.score.score import Score
    from materialyoucolor.hct import Hct
    from materialyoucolor.dynamiccolor.material_dynamic_colors import (
        MaterialDynamicColors,
    )
    from materialyoucolor.scheme.scheme_tonal_spot import SchemeTonalSpot
    from materialyoucolor.scheme.scheme_vibrant import SchemeVibrant
    from materialyoucolor.scheme.scheme_expressive import SchemeExpressive
    from materialyoucolor.scheme.scheme_fruit_salad import SchemeFruitSalad
    from materialyoucolor.scheme.scheme_rainbow import SchemeRainbow
    from materialyoucolor.scheme.scheme_content import SchemeContent

    schemes = {
        "tonalspot": SchemeTonalSpot, "vibrant": SchemeVibrant,
        "expressive": SchemeExpressive, "fruitsalad": SchemeFruitSalad,
        "rainbow": SchemeRainbow, "content": SchemeContent,
    }

    quantized = ImageQuantizeCelebi(str(image), 4, 128)
    seed = Score.score(quantized)[0]
    seed_hct = Hct.from_int(seed)
    scheme = schemes.get(ACCENT_SCHEME, SchemeVibrant)(
        seed_hct, dark, 0.0, spec_version="2025"
    )
    mdc = MaterialDynamicColors(spec="2025")

    def role(name: str) -> str:
        return getattr(mdc, name).get_hex(scheme)[:7]

    def tinted(tone: float, chroma_cap: float) -> str:
        # A colour on the accent's own hue: a genuinely tinted neutral, not
        # Material's near-grey dark surface.
        chroma = min(seed_hct.chroma, chroma_cap)
        return "#%06X" % (Hct.from_hct(seed_hct.hue, chroma, tone).to_int() & 0xFFFFFF)

    # Neutral ramp built from the accent hue. Dark: dark->light; Light: flip.
    if dark:
        ramp = {t: tinted(float(t), 20.0) for t in (8, 14, 18, 22, 26, 30)}
        bg = tinted(BG_TONE, BG_CHROMA_CAP)
        black = tinted(BLACK_TONE, BLACK_CHROMA_CAP)
        greys = {t: tinted(float(t), 10.0) for t in (42, 50, 55, 60)}
    else:
        ramp = {t: tinted(float(t), 12.0) for t in (96, 92, 88, 84, 80, 76)}
        bg = tinted(96.0, min(BG_CHROMA_CAP, 10.0))
        black = tinted(30.0, min(BLACK_CHROMA_CAP, 14.0))
        greys = {t: tinted(float(t), 8.0) for t in (55, 48, 42, 36)}
    gk = sorted(greys)  # ascending tone
    # High-contrast foregrounds (base06/07) — always the lightest in dark mode.
    if dark:
        fg_hi, fg_max = tinted(90.0, 8.0), tinted(97.0, 5.0)
    else:
        fg_hi, fg_max = tinted(30.0, 10.0), tinted(12.0, 8.0)

    accent = {
        "primary": role("primary"),
        "on_primary": role("onPrimary"),
        "primary_container": role("primaryContainer"),
        "on_primary_container": role("onPrimaryContainer"),
        "secondary": role("secondary"),
        "on_secondary": role("onSecondary"),
        "secondary_container": role("secondaryContainer"),
        "on_secondary_container": role("onSecondaryContainer"),
        "tertiary": role("tertiary"),
        "on_tertiary": role("onTertiary"),
        "tertiary_container": role("tertiaryContainer"),
        "on_tertiary_container": role("onTertiaryContainer"),
        "error": role("error"),
    }
    surface = {
        "bg": bg,
        "black": black,
        "fg": role("onSurface"),
        "fg_variant": role("onSurfaceVariant"),
        "outline": role("outline"),
        "selection": accent["primary_container"],
    }

    # base16 slots: neutrals from the tinted ramp, hues fixed (Catppuccin).
    c = CATPPUCCIN
    base16 = {
        "base00": bg,
        "base01": ramp[18 if dark else 92],
        "base02": ramp[26 if dark else 84],
        "base03": surface["outline"],
        "base04": surface["fg_variant"],
        "base05": surface["fg"],
        "base06": fg_hi,
        "base07": fg_max,
        "base08": c["red"],
        "base09": c["peach"],
        "base0A": c["yellow"],
        "base0B": c["green"],
        "base0C": c["teal"],
        "base0D": c["blue"],
        "base0E": c["mauve"],
        "base0F": c["flamingo"],
    }

    return {
        "seed": "#%06X" % (seed & 0xFFFFFF),
        "dark": dark,
        "accent": accent,
        "surface": surface,
        "ramp": {str(t): v for t, v in ramp.items()},
        "greys": {str(t): v for t, v in greys.items()},
        "grey_keys": gk,
        "base16": base16,
        "catppuccin": c,
    }


# --------------------------------------------------------------------------- #
# Emitters
# --------------------------------------------------------------------------- #
def emit_ghostty(pal: dict, image: Path) -> None:
    s, a = pal["surface"], pal["accent"]
    conf = f"""\
# Ghostty wallpaper-accent theme — GENERATED, do not edit by hand.
# Source: {image}
# Appearance: {"dark" if pal["dark"] else "light"}   Seed accent: {pal["seed"]}
#
# Background is the accent hue as a tinted dark; cursor + selection use the
# accent; neutral greys track it. Semantic ANSI hues (red/green/yellow/blue/
# magenta/cyan) stay from the base config so log/diff/ls colours stay legible.

background = {s["bg"]}
foreground = {s["fg"]}

cursor-color = {a["primary"]}
cursor-text = {a["on_primary"]}

selection-background = {a["tertiary_container"]}
selection-foreground = {a["on_tertiary_container"]}

# Neutral greys, accent-tinted (no semantic-hue collision)
palette = 0={s["black"]}
palette = 8={s["outline"]}
palette = 7={s["fg_variant"]}
palette = 15={s["fg"]}
"""
    atomic_write(OUT_CONF, conf)


def emit_fzf(pal: dict) -> None:
    s, a = pal["surface"], pal["accent"]
    color = ",".join(
        [
            f"bg+:{a['secondary_container']}",
            f"bg:{s['bg']}",
            f"fg:{s['fg_variant']}",
            f"fg+:{s['fg']}",
            f"hl:{a['secondary']}",
            f"hl+:{a['secondary']}",
            f"prompt:{a['primary']}",
            f"pointer:{a['primary']}",
            f"marker:{a['tertiary']}",
            f"spinner:{a['tertiary']}",
            f"info:{a['secondary']}",
            f"header:{a['tertiary']}",
            f"border:{s['outline']}",
        ]
    )
    body = f"""\
# GENERATED by wallpaper-accent.py — do not edit. Sourced from .zshrc.local.
export FZF_DEFAULT_OPTS="${{FZF_DEFAULT_OPTS:-}} --color={color}"
"""
    atomic_write(FZF_ENV, body)


def emit_p10k(pal: dict) -> None:
    a = pal["accent"]
    accent = a["primary"]
    body = f"""\
# GENERATED by wallpaper-accent.py — do not edit. Sourced after ~/.p10k.zsh.
# Tints the most prompt-visible segments with the wallpaper accent; extend as
# you like with more POWERLEVEL9K_*_FOREGROUND overrides.
typeset -g POWERLEVEL9K_DIR_FOREGROUND='{accent}'
typeset -g POWERLEVEL9K_DIR_DEFAULT_FOREGROUND='{accent}'
typeset -g POWERLEVEL9K_DIR_SHORTENED_FOREGROUND='{a["secondary"]}'
typeset -g POWERLEVEL9K_DIR_ANCHOR_FOREGROUND='{accent}'
for _wa_s in VIINS VICMD VIVIS VIOWR; do
  typeset -g "POWERLEVEL9K_PROMPT_CHAR_OK_${{_wa_s}}_FOREGROUND"='{a["tertiary"]}'
done
unset _wa_s
"""
    atomic_write(P10K_ZSH, body)


def emit_nvim(pal: dict) -> None:
    b = pal["base16"]
    s, a = pal["surface"], pal["accent"]
    gk = pal["grey_keys"]
    g = pal["greys"]
    ramp = pal["ramp"]
    ttype = "dark" if pal["dark"] else "light"
    # NvChad base46 custom theme. base_16 = syntax (fixed hues + tinted
    # neutrals); base_30 = UI named colours (accent-tinted surfaces).
    base30 = {
        "white": s["fg"],
        "darker_black": ramp[str(8 if pal["dark"] else 96)],
        "black": s["bg"],
        "black2": ramp[str(18 if pal["dark"] else 92)],
        "one_bg": ramp[str(22 if pal["dark"] else 88)],
        "one_bg2": ramp[str(26 if pal["dark"] else 84)],
        "one_bg3": ramp[str(30 if pal["dark"] else 80)],
        "grey": g[str(gk[0])],
        "grey_fg": g[str(gk[1])],
        "grey_fg2": g[str(gk[2])],
        "light_grey": g[str(gk[3])],
        "red": b["base08"],
        "baby_pink": pal["catppuccin"]["flamingo"],
        "pink": pal["catppuccin"]["pink"],
        "line": ramp[str(22 if pal["dark"] else 88)],
        "green": b["base0B"],
        "vibrant_green": b["base0B"],
        "nord_blue": b["base0D"],
        "blue": b["base0D"],
        "yellow": b["base0A"],
        "sun": b["base0A"],
        "purple": b["base0E"],
        "dark_purple": b["base0E"],
        "teal": b["base0C"],
        "orange": b["base09"],
        "cyan": b["base0C"],
        "statusline_bg": ramp[str(14 if pal["dark"] else 92)],
        "lightbg": ramp[str(26 if pal["dark"] else 84)],
        "pmenu_bg": a["primary"],
        "folder_bg": a["secondary"],
    }

    def lua_tbl(d: dict, indent: str = "  ") -> str:
        return "\n".join(f'{indent}{k} = "{v}",' for k, v in d.items())

    body = f"""\
-- GENERATED by wallpaper-accent.py — do not edit by hand.
-- NvChad base46 custom theme from the desktop wallpaper accent ({pal["seed"]}).
local M = {{}}

M.type = "{ttype}"

M.base_30 = {{
{lua_tbl(base30)}
}}

M.base_16 = {{
{lua_tbl(b)}
}}

return M
"""
    atomic_write(NVIM_THEME, body)


def emit_zsh_syntax(pal: dict) -> None:
    b = pal["base16"]
    # fast-syntax-highlighting styles. Fixed semantic hues only (never the
    # accent) so command lines stay legible and varied on any wallpaper:
    # commands blue, builtins teal, strings green, comments grey, errors red.
    styles = {
        "default": f"fg={b['base05']}",
        "unknown-token": f"fg={b['base08']},bold",
        "reserved-word": f"fg={b['base0E']}",
        "subcommand": f"fg={b['base0E']}",
        "alias": f"fg={b['base0C']}",
        "suffix-alias": f"fg={b['base0C']}",
        "global-alias": f"fg={b['base0C']}",
        "builtin": f"fg={b['base0C']}",
        "function": f"fg={b['base0D']}",
        "command": f"fg={b['base0D']}",
        "precommand": f"fg={b['base0E']},italic",
        "hashed-command": f"fg={b['base0D']}",
        "path": f"fg={b['base05']}",
        "path-to-dir": f"fg={b['base05']},underline",
        "path_pathseparator": f"fg={b['base03']}",
        "globbing": f"fg={b['base09']}",
        "single-quoted-argument": f"fg={b['base0B']}",
        "double-quoted-argument": f"fg={b['base0B']}",
        "dollar-quoted-argument": f"fg={b['base0B']}",
        "back-quoted-argument": f"fg={b['base0A']}",
        "single-hyphen-option": f"fg={b['base04']}",
        "double-hyphen-option": f"fg={b['base04']}",
        "variable": f"fg={b['base09']}",
        "dollar-double-quoted-argument": f"fg={b['base09']}",
        "mathvar": f"fg={b['base09']}",
        "mathnum": f"fg={b['base09']}",
        "commandseparator": f"fg={b['base05']}",
        "redirection": f"fg={b['base0E']}",
        "assign": f"fg={b['base05']}",
        "history-expansion": f"fg={b['base0E']}",
        "comment": f"fg={b['base03']},italic",
        "paired-bracket": f"fg={b['base0A']}",
        "bracket-level-1": f"fg={b['base0D']}",
        "bracket-level-2": f"fg={b['base0E']}",
        "bracket-level-3": f"fg={b['base0C']}",
    }
    lines = [
        "# GENERATED by wallpaper-accent — do not edit. Sourced after F-Sy-H loads.",
        "typeset -gA FAST_HIGHLIGHT_STYLES",
    ]
    lines += [f"FAST_HIGHLIGHT_STYLES[{k}]='{v}'" for k, v in styles.items()]
    atomic_write(ZSH_SYNTAX, "\n".join(lines) + "\n")


def emit_colors_json(pal: dict, image: Path) -> None:
    payload = {
        "source": str(image),
        "seed": pal["seed"],
        "scheme": ACCENT_SCHEME,
        "dark": pal["dark"],
        "accent": pal["accent"],
        "surface": pal["surface"],
        "base16": pal["base16"],
    }
    atomic_write(COLORS_JSON, json.dumps(payload, indent=2))


# --------------------------------------------------------------------------- #
# Reload hooks
# --------------------------------------------------------------------------- #
def _pids(procname: str) -> list[int]:
    """Pids whose executable basename == procname. Uses `ps` (pgrep is
    unreliable for GUI apps on this machine)."""
    try:
        out = subprocess.check_output(["ps", "-axo", "pid=,comm="], text=True)
    except Exception as exc:  # noqa: BLE001
        log(f"ps failed: {exc}")
        return []
    pids: list[int] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_str, _, comm = line.partition(" ")
        if os.path.basename(comm.strip()) == procname:
            try:
                pids.append(int(pid_str))
            except ValueError:
                pass
    return pids


def _signal(procname: str, sig: int) -> int:
    n = 0
    for pid in _pids(procname):
        try:
            os.kill(pid, sig)
            n += 1
        except ProcessLookupError:
            pass
        except PermissionError as exc:
            log(f"cannot signal {procname} pid {pid}: {exc}")
    return n


def reload_ghostty() -> None:
    n = _signal("ghostty", signal.SIGUSR2)
    log(f"ghostty: reloaded {n} process(es)" if n else "ghostty: none running")


def reload_nvim() -> None:
    # Running instances re-apply on SIGUSR1 (autocmd) and also refresh the
    # shared base46 disk cache, so future launches inherit the new colours.
    n = _signal("nvim", signal.SIGUSR1)
    if n:
        log(f"nvim: signalled {n} instance(s)")
        return
    # None running: recompile the base46 cache headless so the next launch is
    # themed. Never delete the cache — NvChad's startup dofile()s it directly.
    nvim = shutil.which("nvim")
    if not nvim:
        log("nvim: not installed")
        return
    try:
        subprocess.run(
            [nvim, "--headless", "-c",
             "lua require('base46').load_all_highlights()", "-c", "qa"],
            capture_output=True, timeout=60,
        )
        log("nvim: recompiled base46 cache (headless)")
    except Exception as exc:  # noqa: BLE001
        log(f"nvim: headless recompile failed: {exc}")


# --------------------------------------------------------------------------- #
def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _rgb(hex6: str) -> tuple[int, int, int]:
    h = hex6.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _swatch(hex6: str, label: str) -> str:
    r, g, b = _rgb(hex6)
    fg = "0;0;0" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "255;255;255"
    return f"\x1b[48;2;{r};{g};{b}m\x1b[38;2;{fg}m  {hex6}  \x1b[0m  {label}"


def show_palette() -> int:
    """Print the current palette (from colors.json) as terminal swatches."""
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="regenerate even if the wallpaper is unchanged")
    ap.add_argument("--no-reload", action="store_true",
                    help="write fragments but do not signal apps")
    ap.add_argument("--print", dest="to_stdout", action="store_true",
                    help="print the resolved palette (colors.json) and exit")
    ap.add_argument("--show", action="store_true",
                    help="print the current palette as color swatches and exit")
    ap.add_argument("--image", metavar="PATH",
                    help="use this image instead of the current wallpaper")
    appearance = ap.add_mutually_exclusive_group()
    appearance.add_argument("--dark", action="store_true")
    appearance.add_argument("--light", action="store_true")
    args = ap.parse_args()
    if args.show:
        return show_palette()

    image = Path(args.image).expanduser() if args.image else find_wallpaper()
    if image is None:
        log("wallpaper is not an image (dynamic/aerial/colour); keeping previous theme")
        return 0
    if not image.is_file():
        log(f"wallpaper path does not exist: {image}; keeping previous theme")
        return 0
    dark = True if args.dark else False if args.light else is_dark_appearance()

    key = {"image": str(image), "mtime": image.stat().st_mtime, "dark": dark}
    if (not args.force and not args.to_stdout and COLORS_JSON.is_file()):
        try:
            prev = json.loads(STATE_FILE.read_text())
        except Exception:  # noqa: BLE001
            prev = None
        if prev == key:
            log("wallpaper/appearance unchanged; nothing to do")
            return 0

    pal = build_palette(image, dark)

    if args.to_stdout:
        emit_colors_json(pal, image)  # ensure it reflects latest, then print
        print(COLORS_JSON.read_text())
        return 0

    emit_colors_json(pal, image)
    emit_ghostty(pal, image)
    emit_fzf(pal)
    emit_p10k(pal)
    emit_zsh_syntax(pal)
    emit_nvim(pal)
    atomic_write(STATE_FILE, json.dumps(key, indent=2))
    log(f"themed from {image.name} (accent {pal['seed']}, {'dark' if dark else 'light'})")

    if not args.no_reload:
        reload_ghostty()
        reload_nvim()
        log("fzf/p10k: new shells will pick up the accent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
