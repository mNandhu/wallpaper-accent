"""Dependency-free colour math shared by the palette guards and the reporters.

Pure Python (no ``materialyoucolor``) so it is usable from ``show.py`` / ``cli.py``
— which run without a wallpaper, off ``colors.json`` — as well as from
``palette.py``. HCT-based rotations live in ``palette.py`` (they need the engine);
everything expressible in sRGB/Lab or plain hue degrees lives here.
"""
from __future__ import annotations

from .util import rgb

# --- Lab / ΔE (perceptual distance) ----------------------------------------


def _srgb_to_linear(c: int) -> float:
    x = c / 255.0
    return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4


def lab(hex6: str) -> tuple[float, float, float]:
    """CIE L*a*b* (D65) for a ``#rrggbb`` string."""
    r, g, b = (_srgb_to_linear(v) for v in rgb(hex6))
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x / 0.95047), f(y / 1.0), f(z / 1.08883)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(a: str, b: str) -> float:
    """CIE76 ΔE between two hex colours. <~10 = confusable, >~25 = distinct."""
    la, lb = lab(a), lab(b)
    return sum((x - y) ** 2 for x, y in zip(la, lb)) ** 0.5


# --- WCAG contrast ---------------------------------------------------------


def relative_luminance(hex6: str) -> float:
    r, g, b = (_srgb_to_linear(v) for v in rgb(hex6))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio in [1, 21]."""
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# --- Hue geometry (degrees on the colour wheel) ----------------------------


def hue_distance(a: float, b: float) -> float:
    """Shortest angular distance between two hues, in [0, 180]."""
    d = abs((a - b) % 360.0)
    return min(d, 360.0 - d)


def nearest_allowed_hue(
    hue: float, forbidden: list[float], radius: float
) -> float:
    """Nearest hue to ``hue`` that is at least ``radius`` degrees from every
    hue in ``forbidden``.

    Solves a 1-D circular constraint: the optimum is either ``hue`` itself (if
    already clear) or sits exactly ``radius`` from one of the forbidden hues.
    If no such hue exists (forbidden zones tile the wheel) the original ``hue``
    is returned unchanged.
    """
    def ok(x: float) -> bool:
        return all(hue_distance(x, f) >= radius - 1e-9 for f in forbidden)

    if ok(hue):
        return hue
    candidates = []
    for f in forbidden:
        candidates.append((f + radius) % 360.0)
        candidates.append((f - radius) % 360.0)
    candidates = [c for c in candidates if ok(c)]
    if not candidates:
        return hue
    return min(candidates, key=lambda c: hue_distance(c, hue))
