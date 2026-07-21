"""`install`/`uninstall`: template and (un)load the launchd LaunchAgent.

Generates ~/Library/LaunchAgents/<AGENT_LABEL>.plist from the `uv` actually on
PATH and this repo's actual checkout location, instead of the hand-edited,
hardcoded-path plist previously copy-pasted from the README (see IDEAS.md
"De-hardcode paths"). Then loads it with launchctl so the agent starts firing
on wallpaper change immediately.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import config
from .util import atomic_write, log

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "wallpaper-accent.py"

_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{uv}</string>
    <string>run</string><string>--system-certs</string>
    <string>--no-project</string><string>--script</string>
    <string>{script}</string>
  </array>
  <key>RunAtLoad</key><true/>
  <!-- Fires when the desktop wallpaper changes (macOS rewrites this store). -->
  <key>WatchPaths</key>
  <array>
    <string>{store}</string>
    <string>{index}</string>
  </array>
  <!-- Safety net + catches light/dark flips (no file change). -->
  <key>StartInterval</key><integer>900</integer>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key><string>{home}</string>
    <key>PATH</key><string>{path}</string>{cert}
  </dict>
  <key>ProcessType</key><string>Background</string>
  <key>LimitLoadToSessionType</key><string>Aqua</string>
  <key>StandardOutPath</key><string>{log}</string>
  <key>StandardErrorPath</key><string>{log}</string>
</dict>
</plist>
"""


def _render() -> str:
    uv = shutil.which("uv") or "/opt/homebrew/bin/uv"
    bin_dir = str(Path(uv).parent)
    path = f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin"

    # Belt-and-suspenders for a TLS-MITM'ing proxy (e.g. Zscaler), alongside
    # `--system-certs` — only emitted if this machine actually has one set up.
    cert = ""
    cert_file = os.environ.get("SSL_CERT_FILE")
    if cert_file and Path(cert_file).is_file():
        cert = (
            "\n    <!-- TLS-intercepting proxy on this machine: belt-and-suspenders "
            "alongside --system-certs. -->"
            f"\n    <key>SSL_CERT_FILE</key><string>{cert_file}</string>"
        )

    return _PLIST.format(
        label=config.AGENT_LABEL,
        uv=uv,
        script=str(SCRIPT),
        store=str(config.WALLPAPER_INDEX.parent),
        index=str(config.WALLPAPER_INDEX),
        home=str(config.HOME),
        path=path,
        cert=cert,
        log=str(config.STATE_DIR / "run.log"),
    )


def _target() -> str:
    return f"gui/{os.getuid()}/{config.AGENT_LABEL}"


def _is_loaded() -> bool:
    launchctl = shutil.which("launchctl")
    if not launchctl:
        return False
    return subprocess.run([launchctl, "print", _target()], capture_output=True).returncode == 0


def _bootout() -> None:
    launchctl = shutil.which("launchctl")
    if launchctl:
        subprocess.run([launchctl, "bootout", _target()], capture_output=True)


def _bootstrap() -> int:
    launchctl = shutil.which("launchctl")
    if not launchctl:
        log("launchctl not found (non-macOS?) — plist written but not loaded")
        return 1
    proc = subprocess.run(
        [launchctl, "bootstrap", f"gui/{os.getuid()}", str(config.LAUNCH_AGENT_PLIST)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        log(f"launchctl bootstrap failed: {proc.stderr.strip()}")
        return proc.returncode
    return 0


def install(load: bool = True) -> int:
    """Write the launchd plist (templated from this machine) and load it.

    Reloads (bootout + bootstrap) if the agent is already loaded, so `install`
    doubles as the "apply a plist edit" command — no more manual
    bootout/bootstrap dance.
    """
    if not SCRIPT.is_file():
        log(f"expected shim at {SCRIPT} — is this repo checked out there?")
        return 1
    if not shutil.which("uv"):
        log("uv not on PATH — install/allowlist it first (see README)")
        return 1

    was_loaded = _is_loaded()
    if was_loaded:
        _bootout()
    atomic_write(config.LAUNCH_AGENT_PLIST, _render())
    log(f"wrote {config.LAUNCH_AGENT_PLIST}")

    if not load:
        log("not loaded (--no-load) — `launchctl bootstrap "
            f"gui/{os.getuid()} {config.LAUNCH_AGENT_PLIST}` when ready")
        return 0

    rc = _bootstrap()
    if rc != 0:
        return rc
    log(f"{'reloaded' if was_loaded else 'loaded'} {config.AGENT_LABEL} — "
        "re-themes at login, on wallpaper change, and every 15 min")
    return 0


def uninstall() -> int:
    """Unload the agent and delete its plist."""
    if _is_loaded():
        _bootout()
        log(f"unloaded {config.AGENT_LABEL}")
    if config.LAUNCH_AGENT_PLIST.is_file():
        config.LAUNCH_AGENT_PLIST.unlink()
        log(f"removed {config.LAUNCH_AGENT_PLIST}")
    else:
        log("agent was not installed")
    return 0
