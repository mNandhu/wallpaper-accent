"""Process discovery + signalling.

Uses `ps` rather than `pgrep`: on this machine pgrep silently fails to match
GUI-app processes. `comm` is the full executable path, so we match its basename.
"""
from __future__ import annotations

import os
import subprocess

from .util import log


def pids(procname: str) -> list[int]:
    try:
        out = subprocess.check_output(["ps", "-axo", "pid=,comm="], text=True)
    except Exception as exc:  # noqa: BLE001
        log(f"ps failed: {exc}")
        return []
    found: list[int] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_str, _, comm = line.partition(" ")
        if os.path.basename(comm.strip()) == procname:
            try:
                found.append(int(pid_str))
            except ValueError:
                pass
    return found


def signal_all(procname: str, sig: int) -> int:
    n = 0
    for pid in pids(procname):
        try:
            os.kill(pid, sig)
            n += 1
        except ProcessLookupError:
            pass
        except PermissionError as exc:
            log(f"cannot signal {procname} pid {pid}: {exc}")
    return n
