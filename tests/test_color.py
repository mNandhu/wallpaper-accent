"""Unit tests for the dependency-free colour math (`color.py`).

These are pure functions with exact, known answers — the load-bearing primitives
the palette guards build on. Every test defends an observable contract (a WCAG
ratio, a wraparound distance, the circular-constraint solver's guarantee), not
an implementation detail.
"""
import pytest

from wallpaper_accent.color import (
    contrast_ratio,
    delta_e,
    hue_distance,
    nearest_allowed_hue,
    relative_luminance,
)

WHITE = "#ffffff"
BLACK = "#000000"


# --- ΔE -------------------------------------------------------------------


def test_delta_e_identical_is_zero():
    assert delta_e("#89b4fa", "#89b4fa") == pytest.approx(0.0, abs=1e-9)


def test_delta_e_is_symmetric():
    assert delta_e(WHITE, BLACK) == pytest.approx(delta_e(BLACK, WHITE))


def test_delta_e_black_white_is_lightness_hundred():
    # L* spans 0..100; a==b==0 so ΔE == ΔL* == 100 for black vs white.
    assert delta_e(BLACK, WHITE) == pytest.approx(100.0, abs=1e-6)


def test_delta_e_orders_by_perceptual_closeness():
    near = delta_e("#89b4fa", "#8ab5fb")   # almost the same blue
    far = delta_e("#89b4fa", "#a6e3a1")    # blue vs green
    assert near < far


# --- WCAG contrast / luminance --------------------------------------------


def test_relative_luminance_endpoints():
    assert relative_luminance(WHITE) == pytest.approx(1.0, abs=1e-9)
    assert relative_luminance(BLACK) == pytest.approx(0.0, abs=1e-9)


def test_contrast_black_on_white_is_max():
    assert contrast_ratio(BLACK, WHITE) == pytest.approx(21.0, abs=1e-6)


def test_contrast_is_symmetric_and_identity_is_one():
    assert contrast_ratio("#334455", "#334455") == pytest.approx(1.0)
    assert contrast_ratio(BLACK, WHITE) == pytest.approx(contrast_ratio(WHITE, BLACK))


# --- Hue geometry ---------------------------------------------------------


def test_hue_distance_wraps_around_zero():
    assert hue_distance(350.0, 10.0) == pytest.approx(20.0)
    assert hue_distance(10.0, 350.0) == pytest.approx(20.0)


def test_hue_distance_is_bounded_by_180():
    assert hue_distance(0.0, 180.0) == pytest.approx(180.0)
    assert hue_distance(0.0, 270.0) == pytest.approx(90.0)


def test_hue_distance_identity_is_zero():
    assert hue_distance(42.0, 42.0) == pytest.approx(0.0)


# --- nearest_allowed_hue (1-D circular constraint solver) -----------------


def test_allowed_hue_passthrough_when_already_clear():
    # 50° is 150° from the only forbidden hue -> unchanged.
    assert nearest_allowed_hue(50.0, [200.0], 20.0) == pytest.approx(50.0)


def test_allowed_hue_passthrough_with_no_constraints():
    assert nearest_allowed_hue(123.0, [], 20.0) == pytest.approx(123.0)


def test_allowed_hue_moves_to_nearest_edge_of_zone():
    # 200° sits 10° from forbidden 210°; nearest clearance is 190° (radius 20).
    out = nearest_allowed_hue(200.0, [210.0], 20.0)
    assert out == pytest.approx(190.0)


def test_allowed_hue_guarantees_separation_invariant():
    forbidden = [30.0, 120.0, 210.0, 300.0]
    for hue in range(0, 360, 7):
        out = nearest_allowed_hue(float(hue), forbidden, 20.0)
        assert all(hue_distance(out, f) >= 20.0 - 1e-6 for f in forbidden)


def test_allowed_hue_returns_original_when_wheel_fully_tiled():
    # Forbidden zones of radius 90 at the quadrants tile the whole wheel:
    # no solution exists, so the input hue is returned unchanged.
    assert nearest_allowed_hue(45.0, [0.0, 90.0, 180.0, 270.0], 90.0) == pytest.approx(45.0)
