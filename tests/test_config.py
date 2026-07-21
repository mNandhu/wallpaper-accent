"""Tests for persistent knob configuration (`config.py`).

The contract the `config` subcommand relies on: resolution precedence is
env var > settings file > default, `set_knob` validates + coerces, and
`unset_knob` reverts. Pure stdlib (no materialyoucolor), with SETTINGS_FILE
redirected to a tmp path so real state is never touched.
"""
import pytest

from wallpaper_accent import config


@pytest.fixture(autouse=True)
def tmp_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SETTINGS_FILE", tmp_path / "settings.json")
    # Ensure no ambient env knob leaks into a test.
    for env_var, *_ in config.KNOBS.values():
        monkeypatch.delenv(env_var, raising=False)
    yield


def test_default_when_no_env_no_file():
    assert config.knob_value("bg_chroma") == 22.0
    assert config.knob_source("bg_chroma") == "default"


def test_file_overrides_default():
    stored = config.set_knob("bg_chroma", "6")
    assert stored == 6.0
    assert config.knob_value("bg_chroma") == 6.0
    assert config.knob_source("bg_chroma") == "file"


def test_env_overrides_file(monkeypatch):
    config.set_knob("bg_chroma", "6")
    monkeypatch.setenv("GHOSTTY_ACCENT_BG_CHROMA", "9")
    assert config.knob_value("bg_chroma") == 9.0
    assert config.knob_source("bg_chroma") == "env"


def test_unset_reverts_to_default():
    config.set_knob("bg_chroma", "6")
    assert config.unset_knob("bg_chroma") is True
    assert config.knob_value("bg_chroma") == 22.0
    assert config.knob_source("bg_chroma") == "default"
    # Idempotent: unsetting an absent knob reports nothing removed.
    assert config.unset_knob("bg_chroma") is False


def test_set_coerces_to_declared_type():
    config.set_knob("bg_tone", "10")
    assert config.knob_value("bg_tone") == 10.0
    assert isinstance(config.knob_value("bg_tone"), float)


def test_bad_numeric_value_error_names_the_knob():
    # A raw float() ValueError ("could not convert...") is unhelpful without
    # knowing which knob it came from; set_knob wraps it with the knob name.
    with pytest.raises(ValueError, match="bg_tone.*notanumber"):
        config.set_knob("bg_tone", "notanumber")


def test_scheme_is_validated_and_normalized():
    assert config.set_knob("scheme", "  RaInBoW ") == "rainbow"
    with pytest.raises(ValueError):
        config.set_knob("scheme", "not-a-scheme")


def test_unknown_knob_rejected():
    with pytest.raises(KeyError):
        config.set_knob("nope", "1")
    with pytest.raises(KeyError):
        config.unset_knob("nope")


def test_tuning_signature_reflects_only_resolved_constants():
    # tuning_signature reads the import-time constants; it must contain every
    # knob key so a changed knob busts the idempotency cache.
    sig = config.tuning_signature()
    for key in config.KNOBS:
        assert key in sig
