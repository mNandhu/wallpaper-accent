"""Make the `wallpaper_accent` package importable without an install.

Mirrors the launchd shim (`wallpaper-accent.py`), which prepends `src/` to the
path. Keeps the suite runnable via `uv run --with pytest python -m pytest`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
