"""Tests for the CLI's own logic (`cli.py`): flag parsing/validation and the
small pure-Python subcommand bodies. `_theme`'s wallpaper->palette->component
pipeline is covered end-to-end by manual smoke tests (it touches real
component modules, several of which write outside STATE_DIR); what's tested
here is the part that regressed silently before this change — an unknown
`--only`/`--skip` name used to no-op instead of failing loudly.
"""
import json

import pytest

from wallpaper_accent import cli, components, config


@pytest.fixture(autouse=True)
def tmp_state(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "COLORS_JSON", tmp_path / "colors.json")
    monkeypatch.setattr(config, "STATE_FILE", tmp_path / "state.json")
    yield


def _dummy_image(tmp_path):
    img = tmp_path / "wall.png"
    img.write_bytes(b"not-a-real-png")  # unknown-component check short-circuits before decoding
    return img


def test_only_unknown_component_errors_and_writes_nothing(tmp_path, capsys):
    img = _dummy_image(tmp_path)
    rc = cli.main(["theme", "--image", str(img), "--dark", "--force", "--only", "bogus"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "unknown component" in err
    assert "bogus" in err
    assert not config.COLORS_JSON.exists()  # short-circuited before any write


def test_skip_unknown_component_errors(tmp_path, capsys):
    img = _dummy_image(tmp_path)
    rc = cli.main(["theme", "--image", str(img), "--dark", "--force", "--skip", "bogus"])
    assert rc == 1
    assert "unknown component" in capsys.readouterr().err


def test_only_and_skip_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        cli._build_parser().parse_args(["theme", "--only", "ghostty", "--skip", "fzf"])


def test_version_flag_prints_and_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        cli._build_parser().parse_args(["--version"])
    assert exc.value.code == 0
    assert "wallpaper-accent" in capsys.readouterr().out


def test_components_json_lists_every_registered_component(capsys):
    rc = cli._components(json_out=True)
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    names = {c["name"] for c in data}
    assert names == set(components.REGISTRY)
    ghostty = next(c for c in data if c["name"] == "ghostty")
    assert ghostty["reload"] == "live-reload"
    assert ghostty["enabled"] is True


def test_preview_appearance_flags_are_independent_of_theme_flags():
    ns = cli._build_parser().parse_args(["preview", "img.png", "--light"])
    assert ns.light is True
    # `preview` and `theme` each declare their own --dark/--light group, so
    # this must not collide with theme's.
    ns2 = cli._build_parser().parse_args(["theme", "--dark"])
    assert ns2.dark is True


def test_completion_renders_a_loadable_script_per_shell():
    from wallpaper_accent.completion import render

    bash = render("bash")
    assert "complete -F _wallpaper_accent wallpaper-accent" in bash
    assert "ghostty" in bash and "bg_chroma" in bash  # baked-in component/knob names

    zsh = render("zsh")
    assert zsh.startswith("#compdef wallpaper-accent")

    with pytest.raises(ValueError):
        render("fish")
