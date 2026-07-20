"""`doctor`: verify the machine-local integration points are wired.

The engine is inert until each tool references its generated fragment (ghostty
`config-file`, `.zshrc.local` source lines, nvim chadrc/theme + autocmd, tmux
`source-file`) and the launchd agent is loaded. Those edits live outside this
repo, so "why isn't X theming?" is the common failure. This walks every
prerequisite and integration point and reports OK / WARN / FAIL.

Exit code is non-zero only on a hard FAIL (a missing prerequisite); missing or
un-wired integration is a WARN — inert, not broken.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import components, config

HOME = config.HOME
GHOSTTY_FILES = [HOME / ".config/ghostty/config", HOME / ".config/ghostty/config.local"]
ZSHRC_LOCAL = HOME / "layers/30-local/.zshrc.local"
CHADRC = HOME / ".config/nvim/lua/chadrc.lua"
AUTOCMDS = HOME / ".config/nvim/lua/autocmds.lua"
TMUX_CONF_USER = HOME / ".tmux.conf"

OK, WARN, FAIL = "OK", "WARN", "FAIL"


@dataclass
class Check:
    status: str
    name: str
    detail: str


# Per-component generated fragment + the integration reference(s) that activate
# it. Integration passes if `needle` appears in ANY of `files`.
_FRAGMENTS = {
    "ghostty": config.OUT_CONF,
    "fzf": config.FZF_ENV,
    "p10k": config.P10K_ZSH,
    "zsh-syntax": config.ZSH_SYNTAX,
    "nvim": config.NVIM_THEME,
    "tmux": config.TMUX_CONF,
}
_INTEGRATION = {
    "ghostty": [("ghostty config", GHOSTTY_FILES, "wallpaper-accent/ghostty.conf")],
    "fzf": [(".zshrc.local", [ZSHRC_LOCAL], "fzf.env")],
    "p10k": [(".zshrc.local", [ZSHRC_LOCAL], "p10k-accent.zsh")],
    "zsh-syntax": [(".zshrc.local", [ZSHRC_LOCAL], "zsh-syntax.zsh")],
    "nvim": [
        ("chadrc theme", [CHADRC], "wallpaper_accent"),
        ("SIGUSR1 autocmd", [AUTOCMDS], "SIGUSR1"),
    ],
    "tmux": [("~/.tmux.conf", [TMUX_CONF_USER], "tmux-accent.conf")],
}


def _contains(files: list[Path], needle: str) -> bool:
    for f in files:
        try:
            if needle in f.read_text():
                return True
        except OSError:
            continue
    return False


def _check_uv() -> Check:
    path = shutil.which("uv")
    if path:
        return Check(OK, "uv", path)
    return Check(FAIL, "uv", "not on PATH — the engine cannot run (see README setup)")


def _check_palette() -> Check:
    if not config.COLORS_JSON.is_file():
        return Check(WARN, "palette", "no colors.json yet — run: wallpaper-accent theme --force")
    try:
        d = json.loads(config.COLORS_JSON.read_text())
        appear = "dark" if d.get("dark") else "light"
        return Check(OK, "palette", f"colors.json present (seed {d.get('seed', '?')}, {appear})")
    except (OSError, ValueError) as exc:
        return Check(WARN, "palette", f"colors.json unreadable: {exc}")


def _check_agent() -> list[Check]:
    if not config.LAUNCH_AGENT_PLIST.is_file():
        return [Check(WARN, "launchd", f"plist not installed at {config.LAUNCH_AGENT_PLIST}")]
    launchctl = shutil.which("launchctl")
    if not launchctl:
        return [Check(WARN, "launchd", "launchctl not found (non-macOS?)")]
    target = f"gui/{os.getuid()}/{config.AGENT_LABEL}"
    rc = subprocess.run([launchctl, "print", target], capture_output=True).returncode
    if rc == 0:
        return [Check(OK, "launchd", f"agent loaded ({config.AGENT_LABEL})")]
    return [Check(WARN, "launchd", f"agent not loaded — launchctl bootstrap gui/{os.getuid()} {config.LAUNCH_AGENT_PLIST}")]


def _check_component(name: str) -> list[Check]:
    out: list[Check] = []
    frag = _FRAGMENTS.get(name)
    if frag is not None:
        if frag.is_file():
            out.append(Check(OK, f"{name}: fragment", str(frag)))
        else:
            out.append(Check(WARN, f"{name}: fragment", f"{frag} not generated yet"))
    for label, files, needle in _INTEGRATION.get(name, []):
        if _contains(files, needle):
            out.append(Check(OK, f"{name}: {label}", f"references '{needle}'"))
        else:
            loc = files[0] if len(files) == 1 else "/".join(f.name for f in files)
            out.append(Check(WARN, f"{name}: {label}", f"no reference to '{needle}' in {loc}"))
    return out


def run() -> int:
    checks: list[Check] = [_check_uv(), _check_palette()]
    checks += _check_agent()
    for name in config.enabled_component_names():
        if name not in components.REGISTRY:
            checks.append(Check(WARN, name, "enabled but unknown component"))
            continue
        checks += _check_component(name)

    color = {OK: "\x1b[32m", WARN: "\x1b[33m", FAIL: "\x1b[31m"}
    reset = "\x1b[0m"
    print("\n  wallpaper-accent doctor\n")
    width = max(len(c.name) for c in checks)
    for c in checks:
        tag = f"{color[c.status]}{c.status:4}{reset}"
        print(f"  [{tag}] {c.name.ljust(width)}  {c.detail}")
    n_ok = sum(c.status == OK for c in checks)
    n_warn = sum(c.status == WARN for c in checks)
    n_fail = sum(c.status == FAIL for c in checks)
    print(f"\n  {n_ok} ok, {n_warn} warning(s), {n_fail} failed\n")
    return 1 if n_fail else 0
