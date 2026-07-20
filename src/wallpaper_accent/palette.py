"""Core: turn a wallpaper image into a full palette dict.

The returned `pal` is the single source of truth every component reads from
(and what `colors.json` mirrors). Accent hues come from a Material scheme
(harmony); backgrounds/greys are built on the accent's own HCT hue; the base16
color slots (base08..base0F) stay on fixed Catppuccin hues for legibility.
"""
from __future__ import annotations

from pathlib import Path

from . import config


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
    scheme = schemes.get(config.ACCENT_SCHEME, SchemeVibrant)(
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
        bg = tinted(config.BG_TONE, config.BG_CHROMA_CAP)
        black = tinted(config.BLACK_TONE, config.BLACK_CHROMA_CAP)
        greys = {t: tinted(float(t), 10.0) for t in (42, 50, 55, 60)}
    else:
        ramp = {t: tinted(float(t), 12.0) for t in (96, 92, 88, 84, 80, 76)}
        bg = tinted(96.0, min(config.BG_CHROMA_CAP, 10.0))
        black = tinted(30.0, min(config.BLACK_CHROMA_CAP, 14.0))
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
    c = config.CATPPUCCIN
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
        "source": str(image),
        "scheme": config.ACCENT_SCHEME,
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
