"""End-to-end invariant test for `build_palette`.

Feeds a synthetic solid-colour wallpaper through the whole pipeline (quantize ->
seed -> scheme -> guards) and asserts the load-bearing contracts hold — most
importantly on an *adversarial* wallpaper whose dominant hue is a syntax hue
(vivid blue vs Catppuccin blue): the accent must still separate from every fixed
syntax hue. This is the golden-palette regression guard for the guard stack.
"""
import struct
import zlib

import pytest

from wallpaper_accent import config
from wallpaper_accent.color import contrast_ratio
from wallpaper_accent.palette import build_palette, collision_report


def _solid_png(path, rgb, size=16):
    r, g, b = rgb
    row = b"\x00" + bytes([r, g, b]) * size          # filter byte 0 + RGB pixels
    raw = row * size

    def chunk(typ, data):
        body = typ + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)   # 8-bit RGB
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    return path


@pytest.fixture
def blue_wallpaper(tmp_path):
    # Vivid blue — collides head-on with Catppuccin syntax blue (#89b4fa).
    return _solid_png(tmp_path / "blue.png", (0x1E, 0x66, 0xF5))


def test_palette_has_full_contract(blue_wallpaper):
    pal = build_palette(blue_wallpaper, dark=True)
    for key in ("seed", "accent", "surface", "base16", "ramp", "greys"):
        assert key in pal
    assert pal["dark"] is True
    assert pal["seed"].startswith("#") and len(pal["seed"]) == 7


def test_accent_separated_from_syntax_hues_on_blue_wallpaper(blue_wallpaper):
    # The guard's whole reason to exist: a blue wallpaper must not make the
    # accent impersonate syntax blue. collision_report empty == guards held.
    assert config.MIN_HUE_SEP > 0
    assert config.ACCENT_SCHEME not in config.MONOCHROMATIC_SCHEMES
    pal = build_palette(blue_wallpaper, dark=True)
    assert collision_report(pal) == []


def test_foreground_clears_contrast_over_background(blue_wallpaper):
    pal = build_palette(blue_wallpaper, dark=True)
    s = pal["surface"]
    assert contrast_ratio(s["fg"], s["bg"]) >= config.FG_MIN_CONTRAST
    assert contrast_ratio(s["fg_variant"], s["bg"]) >= config.FG_VARIANT_MIN_CONTRAST


def test_single_selection_source(blue_wallpaper):
    # Every component reads surface.selection; it must be the tertiary container.
    pal = build_palette(blue_wallpaper, dark=True)
    assert pal["surface"]["selection"] == pal["accent"]["tertiary_container"]
    assert pal["surface"]["on_selection"] == pal["accent"]["on_tertiary_container"]


def test_syntax_hues_stay_fixed_catppuccin(blue_wallpaper):
    # Non-monochromatic scheme -> base08..base0F are the fixed Catppuccin hues,
    # untouched by the accent (the invariant that keeps logs/diffs/code legible).
    pal = build_palette(blue_wallpaper, dark=True)
    b16, c = pal["base16"], config.CATPPUCCIN
    assert b16["base08"] == c["red"]
    assert b16["base0B"] == c["green"]
    assert b16["base0D"] == c["blue"]
    assert b16["base0F"] == c["flamingo"]
