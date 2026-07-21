"""Tests for palette history (`theme --undo`).

Contract `history.py` provides: `advance(pal)` records a real theme change
(pushing the outgoing current onto a capped ring, skipping same-accent
re-runs); `undo()` walks straight back through that ring without oscillating
between the last two themes. Redirects HISTORY_FILE/LAST_PALETTE_FILE to a
tmp path so real state is never touched.
"""
import json

import pytest

from wallpaper_accent import config, history


@pytest.fixture(autouse=True)
def tmp_history(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(config, "LAST_PALETTE_FILE", tmp_path / "last_palette.json")
    monkeypatch.setattr(config, "HISTORY_MAX", 3)
    yield


def _pal(seed, dark=True, scheme="content"):
    return {"seed": seed, "scheme": scheme, "dark": dark, "source": f"{seed}.png"}


def test_current_is_none_before_any_theme():
    assert history.current() is None


def test_advance_sets_current_without_a_ring_on_first_call():
    history.advance(_pal("#111111"))
    assert history.current() == _pal("#111111")
    assert history.undo() is None  # nothing to go back to yet


def test_undo_restores_the_immediately_prior_palette():
    history.advance(_pal("#111111"))
    history.advance(_pal("#222222"))
    restored = history.undo()
    assert restored == _pal("#111111")
    assert history.current() == _pal("#111111")


def test_repeated_undo_walks_further_back_without_oscillating():
    history.advance(_pal("#111111"))
    history.advance(_pal("#222222"))
    history.advance(_pal("#333333"))
    assert history.undo() == _pal("#222222")
    assert history.undo() == _pal("#111111")
    assert history.undo() is None  # exhausted


def test_advance_skips_pushing_a_duplicate_same_accent_rerun():
    history.advance(_pal("#111111"))
    history.advance(_pal("#111111"))  # e.g. `--force` re-run of the same wallpaper
    assert history.undo() is None


def test_ring_is_capped_at_history_max():
    for i in range(5):
        history.advance(_pal(f"#{i:06x}"))
    ring = json.loads(config.HISTORY_FILE.read_text())
    assert len(ring) == config.HISTORY_MAX  # oldest entries dropped, not the current one
