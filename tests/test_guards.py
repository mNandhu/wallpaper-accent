"""Tests for the palette guards (`palette.py`) — the functions that keep the
invariant usable on adversarial wallpapers.

Each guard has a crisp post-condition the emitters rely on:
  * repel_accent   -> every accent role ends >= sep from every fixed syntax hue
  * nudge_semantics-> every semantic slot ends >= sep from every accent hue
  * enforce_contrast -> fg/fg_variant clear their WCAG floor over the bg
  * collision_report -> flags a role confusable with a syntax hue, else silent

These need `materialyoucolor` (HCT rotations), so they live apart from the pure
`color.py` tests.
"""
import pytest

from wallpaper_accent import config
from wallpaper_accent.color import contrast_ratio, hue_distance
from wallpaper_accent.palette import (
    SEMANTIC_SLOTS,
    _hct,
    _hex_from_hct,
    collision_report,
    enforce_contrast,
    nudge_semantics,
    spread_secondary,
    repel_accent,
)

SEP = 20.0
SEMANTIC_HUES = [_hct(config.CATPPUCCIN[n]).hue for n in SEMANTIC_SLOTS.values()]
# HCT<->sRGB gamut round-trip drifts realized hues by a fraction of a degree;
# guard post-conditions hold "within slack", never bit-exactly.
HCT_SLACK = 1.0


def _accent(p_hue, s_hue, t_hue, chroma=48.0, tone=60.0):
    """A full 13-key accent dict with each role group pinned to one hue."""
    def grp(prefix, hue):
        return {
            prefix: _hex_from_hct(hue, chroma, tone),
            f"on_{prefix}": _hex_from_hct(hue, chroma, min(tone + 30, 100)),
            f"{prefix}_container": _hex_from_hct(hue, chroma, max(tone - 20, 0)),
            f"on_{prefix}_container": _hex_from_hct(hue, chroma, min(tone + 35, 100)),
        }
    out = {"error": _hex_from_hct(25.0, chroma, tone)}
    out.update(grp("primary", p_hue))
    out.update(grp("secondary", s_hue))
    out.update(grp("tertiary", t_hue))
    return out


# --- repel_accent ---------------------------------------------------------


@pytest.mark.parametrize("collide_hue", SEMANTIC_HUES)
def test_repel_separates_every_role_from_every_syntax_hue(collide_hue):
    # Seed all three roles directly on a syntax hue -> maximally adversarial.
    accent = _accent(collide_hue, collide_hue, collide_hue)
    repel_accent(accent, SEMANTIC_HUES, SEP)
    # Realized hues drift ~0.3 deg through the HCT<->sRGB gamut round-trip, so
    # allow 1 deg slack: the contract is "close to SEP apart", not exact.
    for role in ("primary", "secondary", "tertiary"):
        h = _hct(accent[role]).hue
        assert all(hue_distance(h, f) >= SEP - HCT_SLACK for f in SEMANTIC_HUES), role


def test_repel_leaves_already_clear_accent_untouched():
    # 210° (fallback hue) sits in the teal->blue gap, clear of all syntax hues.
    clear = 210.0
    assert all(hue_distance(clear, f) >= SEP for f in SEMANTIC_HUES)
    accent = _accent(clear, clear, clear)
    before = dict(accent)
    repel_accent(accent, SEMANTIC_HUES, SEP)
    assert accent == before


def test_repel_rotates_role_group_coherently():
    # The whole group shares one delta, so on_/container members track the base.
    collide = SEMANTIC_HUES[0]
    accent = _accent(collide, 210.0, 210.0)
    base_before = _hct(accent["primary"]).hue
    cont_before = _hct(accent["primary_container"]).hue
    repel_accent(accent, SEMANTIC_HUES, SEP)
    base_after = _hct(accent["primary"]).hue
    cont_after = _hct(accent["primary_container"]).hue
    d_base = hue_distance(base_before, base_after)
    d_cont = hue_distance(cont_before, cont_after)
    assert d_base > 1e-6
    assert d_base == pytest.approx(d_cont, abs=1.0)


# --- spread_secondary -----------------------------------------------------


def test_spread_secondary_rotates_group_to_offset_from_primary():
    # Scheme collapses secondary onto primary's hue; spread must push it to
    # primary + offset so the accent is genuinely tri-hue.
    accent = _accent(120.0, 120.0, 220.0)
    offset = 40.0
    spread_secondary(accent, offset)
    p = _hct(accent["primary"]).hue
    s = _hct(accent["secondary"]).hue
    assert hue_distance(s, (p + offset) % 360.0) <= HCT_SLACK
    # Whole group tracks one shared delta.
    for m in ("on_secondary", "secondary_container", "on_secondary_container"):
        assert hue_distance(_hct(accent[m]).hue, s) <= HCT_SLACK
    # Primary and tertiary are untouched.
    assert hue_distance(_hct(accent["primary"]).hue, 120.0) <= HCT_SLACK
    assert hue_distance(_hct(accent["tertiary"]).hue, 220.0) <= HCT_SLACK


# --- nudge_semantics ------------------------------------------------------


def test_nudge_moves_syntax_hues_off_a_monochromatic_accent():
    base16 = {slot: config.CATPPUCCIN[name] for slot, name in SEMANTIC_SLOTS.items()}
    # Single-hue accent parked right on syntax blue.
    accent_hues = [_hct(config.CATPPUCCIN["blue"]).hue]
    nudge_semantics(base16, accent_hues, SEP)
    for slot in SEMANTIC_SLOTS:
        h = _hct(base16[slot]).hue
        assert all(hue_distance(h, a) >= SEP - HCT_SLACK for a in accent_hues), slot


# --- enforce_contrast -----------------------------------------------------


def test_enforce_contrast_lifts_low_contrast_foregrounds_on_dark_bg():
    bg = _hex_from_hct(210.0, 20.0, config.BG_TONE)     # tinted dark bg
    surface = {
        "fg": _hex_from_hct(210.0, 20.0, config.BG_TONE + 4),        # too close
        "fg_variant": _hex_from_hct(210.0, 20.0, config.BG_TONE + 3),
    }
    assert contrast_ratio(surface["fg"], bg) < config.FG_MIN_CONTRAST
    enforce_contrast(surface, bg, dark=True)
    assert contrast_ratio(surface["fg"], bg) >= config.FG_MIN_CONTRAST
    assert contrast_ratio(surface["fg_variant"], bg) >= config.FG_VARIANT_MIN_CONTRAST


def test_enforce_contrast_leaves_already_legible_foreground_untouched():
    bg = _hex_from_hct(210.0, 20.0, config.BG_TONE)
    good = _hex_from_hct(210.0, 8.0, 92.0)              # bright fg, ample contrast
    surface = {"fg": good, "fg_variant": good}
    assert contrast_ratio(good, bg) >= config.FG_MIN_CONTRAST
    enforce_contrast(surface, bg, dark=True)
    assert surface["fg"] == good


# --- collision_report -----------------------------------------------------


def test_collision_report_flags_role_on_a_syntax_hue():
    colors = {
        "accent": {
            "primary": config.CATPPUCCIN["red"],   # identical to base08
            "secondary": "#ffffff",
            "tertiary": "#ffffff",
        },
        "base16": {"base08": config.CATPPUCCIN["red"]},
    }
    hits = collision_report(colors)
    assert any("primary" in h and "base08" in h for h in hits)


def test_collision_report_silent_when_roles_are_distinct():
    base16 = {slot: config.CATPPUCCIN[name] for slot, name in SEMANTIC_SLOTS.items()}
    colors = {
        "accent": {"primary": "#ffffff", "secondary": "#fefefe", "tertiary": "#fdfdfd"},
        "base16": base16,
    }
    assert collision_report(colors) == []
