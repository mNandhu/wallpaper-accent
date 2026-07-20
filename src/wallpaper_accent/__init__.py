"""Theme terminal tools from the macOS desktop wallpaper's accent color.

Package layout:
    config.py       paths, tint/scheme knobs, CATPPUCCIN, enabled components
    util.py         log, atomic_write, rgb
    procs.py        ps-based pid lookup + signalling (pgrep is unreliable here)
    wallpaper.py    macOS glue: current wallpaper path + light/dark
    palette.py      core: image -> full palette dict
    components/      one module per themed tool (emit + optional reload)
    show.py         --show swatch renderer
    cli.py          argparse + orchestration (main)
"""

__version__ = "0.1.0"
