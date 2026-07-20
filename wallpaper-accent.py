#!/usr/bin/env -S uv run --system-certs --no-project --script
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = ["materialyoucolor>=3.0.2"]
# ///
"""Entry point for the launchd agent / shebang.

Thin shim: adds `src/` to the path and delegates to the package. Deps are
provisioned by uv from the PEP-723 block above (kept in sync with
pyproject.toml). The real code lives in src/wallpaper_accent/ — see that package
and ARCHITECTURE.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from wallpaper_accent.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
