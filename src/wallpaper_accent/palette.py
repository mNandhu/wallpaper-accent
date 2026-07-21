"""Core: turn a wallpaper image into a full palette dict.

The returned `pal` is the single source of truth every component reads from
(and what `colors.json` mirrors). Accent hues come from a Material scheme
(harmony); backgrounds/greys are built on the accent's own HCT hue; the base16
color slots (base08..base0F) stay on fixed Catppuccin hues for legibility.

Five guards keep the palette usable on adversarial wallpapers (see the module
functions and ARCHITECTURE.md "Palette guards"):
  * robust seed selection — skip near-grey quantized colours;
  * chroma floor / greyscale fallback — dull wallpapers still get a live accent;
  * hue de-confliction — the accent never impersonates a fixed syntax hue
    (repel the accent for spread schemes; nudge the syntax hue for
    monochromatic ones);
  * contrast enforcement — foregrounds stay legible over the tinted background;
  * one selection colour, sourced here and consumed by every component.
"""
from __future__ import annotations

from pathlib import Path

from . import config
from .color import contrast_ratio, delta_e, nearest_allowed_hue

# base16 syntax slots whose hue is FIXED (the ones that visually collide with an
# accent). slot -> Catppuccin key. base00..base07 are tinted neutrals, not here.
SEMANTIC_SLOTS = {
    "base08": "red", "base09": "peach", "base0A": "yellow", "base0B": "green",
    "base0C": "teal", "base0D": "blue", "base0E": "mauve", "base0F": "pink",
}


def collision_report(colors: dict) -> list[str]:
    """Diagnostic (#2): accent roles that are perceptually confusable with a
    fixed syntax hue (ΔE < REPORT_DE_THRESHOLD). Empty when the guards did their
    job; non-empty flags a wallpaper the guard could not fully separate (e.g.
    guard disabled, or a monochromatic scheme pinned to a syntax hue)."""
    accent, base16 = colors.get("accent", {}), colors.get("base16", {})
    out: list[str] = []
    for role in ("primary", "secondary", "tertiary"):
        if role not in accent:
            continue
        for slot, name in SEMANTIC_SLOTS.items():
            if slot not in base16:
                continue
            d = delta_e(accent[role], base16[slot])
            if d < config.REPORT_DE_THRESHOLD:
                out.append(f"{role} ≈ {slot} ({name}) ΔE {d:.1f}")
    return out


def _hct(hex6: str):
    from materialyoucolor.hct import Hct

    return Hct.from_int((0xFF << 24) | (int(hex6.lstrip("#"), 16) & 0xFFFFFF))


def _hex_from_hct(hue: float, chroma: float, tone: float) -> str:
    from materialyoucolor.hct import Hct

    return "#%06X" % (Hct.from_hct(hue, chroma, tone).to_int() & 0xFFFFFF)


def _select_seed(quantized):
    """Most prominent sufficiently-colourful quantized colour (#6 stability).

    Score ranks by prominence; we skip near-grey candidates so a colourful photo
    with a large dull region still seeds from its actual colour and does not
    flip-flop into a washed-out accent. Falls back to the top candidate (the
    greyscale guard in build_palette then handles the dull hue)."""
    from materialyoucolor.hct import Hct
    from materialyoucolor.score.score import Score, ScoreOptions

    ranked = Score.score(quantized, ScoreOptions(desired=8, filter=False))
    hcts = [Hct.from_int(c) for c in ranked]
    for h in hcts:
        if h.chroma >= config.CHROMA_FLOOR:
            return h
    return hcts[0]


_QUANTIZE_CACHE: dict = {}


def _quantize(image: Path):
    """Quantize an image to its dominant colours — the expensive, knob-INDEPENDENT
    step. Cached by (path, mtime) so the live `config edit` editor can rebuild the
    palette on every keystroke without re-reading the image. Seed selection stays
    outside the cache (it reads CHROMA_FLOOR) so that knob still previews live."""
    key = (str(image), image.stat().st_mtime)
    cached = _QUANTIZE_CACHE.get(key)
    if cached is None:
        from materialyoucolor.quantize import ImageQuantizeCelebi

        cached = ImageQuantizeCelebi(str(image), 4, 128)
        _QUANTIZE_CACHE[key] = cached
    return cached


def _accent_seed(seed_hct):
    """Seed handed to the Material scheme (#4 chroma floor / greyscale fallback).

    A near-grey wallpaper has a dull or (near 0) meaningless hue. Lift chroma to
    a floor so the scheme yields a live accent; if the hue itself is unreliable,
    substitute FALLBACK_HUE. Neutrals keep the *original* seed (so a grey
    wallpaper stays tastefully neutral) — only the accent is boosted."""
    if seed_hct.chroma >= config.CHROMA_FLOOR:
        return seed_hct
    hue = seed_hct.hue if seed_hct.chroma >= config.GREY_HUE_CHROMA else config.FALLBACK_HUE
    from materialyoucolor.hct import Hct

    return Hct.from_hct(hue, max(seed_hct.chroma, 48.0), seed_hct.tone)


def _signed_delta(old: float, new: float) -> float:
    return ((new - old + 180.0) % 360.0) - 180.0


def repel_accent(accent: dict, semantic_hues: list[float], sep: float) -> None:
    """#1 — rotate each accent role group away from every fixed syntax hue.

    Each role (primary/secondary/tertiary) and its on-/container members are
    rotated by one shared delta, so the coordinated tone/contrast relationships
    Material built survive; only the hue family moves off the syntax hue."""
    groups = {
        "primary": ("primary", "on_primary", "primary_container", "on_primary_container"),
        "secondary": ("secondary", "on_secondary", "secondary_container", "on_secondary_container"),
        "tertiary": ("tertiary", "on_tertiary", "tertiary_container", "on_tertiary_container"),
    }
    for rep, members in groups.items():
        old = _hct(accent[rep]).hue
        delta = _signed_delta(old, nearest_allowed_hue(old, semantic_hues, sep))
        if abs(delta) < 1e-6:
            continue
        for m in members:
            c = _hct(accent[m])
            accent[m] = _hex_from_hct(c.hue + delta, c.chroma, c.tone)


def spread_secondary(accent: dict, offset: float) -> None:
    """Rotate the secondary role group to a fixed hue offset from primary.

    Material's spread schemes tie `secondary` to the primary hue (a desaturated
    sibling), so without this the accent is really two hue families (primary +
    tertiary), not three. Rotating the whole secondary group by one shared delta
    — same coherent-group technique as `repel_accent` — yields a genuinely
    tri-hue accent. Runs before `repel_accent`, which then de-conflicts the
    rotated hue from the fixed syntax hues, so the invariant still holds."""
    members = ("secondary", "on_secondary", "secondary_container", "on_secondary_container")
    target = (_hct(accent["primary"]).hue + offset) % 360.0
    delta = _signed_delta(_hct(accent["secondary"]).hue, target)
    if abs(delta) < 1e-6:
        return
    for m in members:
        c = _hct(accent[m])
        accent[m] = _hex_from_hct(c.hue + delta, c.chroma, c.tone)


def nudge_semantics(base16: dict, accent_hues: list[float], sep: float) -> None:
    """#8 — for monochromatic schemes, move the *syntax* hue off the accent.

    Preserves the single-hue accent aesthetic (tonalspot): rather than fighting
    the scheme, the few syntax slots that collide are rotated to the nearest hue
    clear of the accent, keeping their Catppuccin tone/chroma (still legible)."""
    for slot in SEMANTIC_SLOTS:
        c = _hct(base16[slot])
        nh = nearest_allowed_hue(c.hue, accent_hues, sep)
        if abs(_signed_delta(c.hue, nh)) > 1e-6:
            base16[slot] = _hex_from_hct(nh, c.chroma, c.tone)


def enforce_contrast(surface: dict, bg: str, dark: bool) -> None:
    """#3 — lift foreground tones until they clear WCAG contrast over `bg`.

    Our tinted `bg` overrides Material's `surface`, so Material's onSurface /
    onSurfaceVariant are not guaranteed legible against it. Walk the tone toward
    the contrasting end (lighter on dark bg, darker on light) until it clears."""
    step = 2.0 if dark else -2.0
    for key, minc in (("fg", config.FG_MIN_CONTRAST),
                      ("fg_variant", config.FG_VARIANT_MIN_CONTRAST)):
        if contrast_ratio(surface[key], bg) >= minc:
            continue
        c = _hct(surface[key])
        tone = c.tone
        for _ in range(50):
            tone = max(0.0, min(100.0, tone + step))
            cand = _hex_from_hct(c.hue, c.chroma, tone)
            if contrast_ratio(cand, bg) >= minc:
                surface[key] = cand
                break
            if tone in (0.0, 100.0):
                surface[key] = cand
                break


def build_palette(image: Path, dark: bool) -> dict:
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

    quantized = _quantize(image)
    seed_hct = _select_seed(quantized)          # #6 robust seed
    seed = seed_hct.to_int()
    accent_seed = _accent_seed(seed_hct)        # #4 chroma floor / fallback
    scheme = schemes.get(config.ACCENT_SCHEME, SchemeVibrant)(
        accent_seed, dark, 0.0, spec_version="2025"
    )
    mdc = MaterialDynamicColors(spec="2025")

    def role(name: str) -> str:
        return getattr(mdc, name).get_hex(scheme)[:7]

    def tinted(tone: float, chroma_cap: float) -> str:
        # A colour on the seed's own hue: a genuinely tinted neutral, not
        # Material's near-grey dark surface.
        chroma = min(seed_hct.chroma, chroma_cap)
        return _hex_from_hct(seed_hct.hue, chroma, tone)

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

    # Hue de-confliction. Spread schemes rotate the accent off the syntax hues
    # (#1); monochromatic schemes instead nudge the syntax hues later (#8) so
    # the single-hue accent aesthetic survives.
    semantic_hues = [_hct(config.CATPPUCCIN[n]).hue for n in SEMANTIC_SLOTS.values()]
    monochromatic = config.ACCENT_SCHEME in config.MONOCHROMATIC_SCHEMES
    if config.SECONDARY_SPREAD > 0 and not monochromatic:
        spread_secondary(accent, config.SECONDARY_SPREAD)
    if config.MIN_HUE_SEP > 0 and not monochromatic:
        repel_accent(accent, semantic_hues, config.MIN_HUE_SEP)

    surface = {
        "bg": bg,
        "black": black,
        "fg": role("onSurface"),
        "fg_variant": role("onSurfaceVariant"),
        "outline": role("outline"),
        # One selection colour, sourced here (#7). tertiary_container keeps
        # selection distinct from the cursor (primary). Every component reads
        # surface["selection"]/["on_selection"] — no per-tool hardcoding.
        "selection": accent["tertiary_container"],
        "on_selection": accent["on_tertiary_container"],
    }
    enforce_contrast(surface, bg, dark)          # #3 legible foregrounds

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
        "base0F": c["pink"],
    }
    if config.MIN_HUE_SEP > 0 and monochromatic:
        accent_hues = [_hct(accent[k]).hue for k in ("primary", "secondary", "tertiary")]
        nudge_semantics(base16, accent_hues, config.MIN_HUE_SEP)

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
