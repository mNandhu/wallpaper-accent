# wallpaper-accent

Theme terminal tools from the macOS desktop wallpaper's accent color. When the
wallpaper changes, a background agent derives a Material You palette from the
image and re-themes **ghostty, fzf, powerlevel10k, fast-syntax-highlighting, and
neovim (NvChad)**, hot-reloading whatever is running.

Self-contained repo (its own git repo under `~/.config`, independent of the
dotfiles layers) so the whole stack — engine + docs — lives in one place and can
grow into a CLI. Active on this (Work) Mac only; activation is machine-local.
Engineering/extension reference: [`ARCHITECTURE.md`](./ARCHITECTURE.md).

> Uses a Python engine (`materialyoucolor` via `uv`), not `matugen`: matugen has
> no arm64 macOS binary and a cargo build is killed by Airlock (app
> allowlisting). `uv`/Python are allowlisted.

---

## Layout

```
~/.config/wallpaper-accent/          <- this git repo
  wallpaper-accent.py                <- the engine (core + emitters + reloads)
  README.md  ARCHITECTURE.md
~/.local/state/wallpaper-accent/     <- generated output (not in the repo)
  colors.json      <- shared palette (source of truth)
  ghostty.conf  fzf.env  p10k-accent.zsh  zsh-syntax.zsh
  state.json  run.log
~/.config/nvim/lua/themes/wallpaper_accent.lua   <- generated (must be in nvim rtp)
```

Architecture: one core extracts the accent → `colors.json`; per-app emitters
render fragments; per-app reload hooks apply them.

---

## Per-app behavior

| App | What follows the accent | Reload of running instances |
|---|---|---|
| **ghostty** | bg, fg, cursor, selection, greys | **live** — `SIGUSR2` |
| **nvim** (NvChad) | UI surfaces, statusline, popup, greys; syntax fixed | **live** — `SIGUSR1` autocmd |
| **fzf** | prompt/pointer/hl/bg+/border | new shells |
| **p10k** | directory path + prompt char | new shells |
| **fast-syntax-highlighting** | *not the accent* — a fixed, varied syntax theme (commands blue, builtins teal, strings green, comments grey, errors red) | new shells |

Design rule: the accent drives **surfaces / greys / cursor / selection / accent-y
UI**; **semantic hues stay fixed** (Catppuccin red/green/yellow/blue/magenta/cyan
+ all code syntax) so logs, diffs, `ls`, and code stay legible under any wallpaper.
Distinct accent hues (primary/secondary/tertiary) are spread across roles so a
green wallpaper isn't uniformly green.

---

## How-to

The script is executable (its shebang runs `uv --system-certs`):

```bash
# Re-theme everything from the current wallpaper:
~/.config/wallpaper-accent/wallpaper-accent.py --force

# Show the current palette as color swatches in the terminal:
~/.config/wallpaper-accent/wallpaper-accent.py --show

# Preview any image (writes nothing, prints the palette JSON):
~/.config/wallpaper-accent/wallpaper-accent.py --image ~/Pictures/foo.png --print

# Apply a specific image / skip app reloads:
~/.config/wallpaper-accent/wallpaper-accent.py --image ~/Pictures/foo.png --force
~/.config/wallpaper-accent/wallpaper-accent.py --force --no-reload
```

### Diversify / tune the colors (env vars)

**Harmony** — how varied the accent is (one wallpaper color → primary + secondary
+ tertiary; the scheme sets how far apart their hues are).

| Var | Default | Effect |
|---|---|---|
| `GHOSTTY_ACCENT_SCHEME` | `vibrant` | `vibrant` (distinct hues), `tonalspot` (monochromatic — one hue), `expressive`, `fruitsalad`, `rainbow`, `content` |

**Tint** — HCT: **tone** = lightness (0–100), **chroma** = colorfulness.

| Var | Default | Effect |
|---|---|---|
| `GHOSTTY_ACCENT_BG_CHROMA` | `22` | ↑ = more saturated background |
| `GHOSTTY_ACCENT_BG_TONE` | `14` | ↓ = darker background |
| `GHOSTTY_ACCENT_BLACK_CHROMA` | `18` | tint of ANSI "black" / darkest greys |
| `GHOSTTY_ACCENT_BLACK_TONE` | `22` | lightness of ANSI "black" |

One-off: `GHOSTTY_ACCENT_SCHEME=rainbow ~/.config/wallpaper-accent/wallpaper-accent.py --force`
Permanent: add under `EnvironmentVariables` in the launchd plist, then reload the agent.

### Reload the launchd agent (after editing the plist)
```bash
launchctl bootout   gui/$(id -u)/com.kmurthi.wallpaper-accent
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.kmurthi.wallpaper-accent.plist
```

### Status / debug
```bash
cat ~/.local/state/wallpaper-accent/run.log
~/.config/wallpaper-accent/wallpaper-accent.py --show
launchctl print gui/$(id -u)/com.kmurthi.wallpaper-accent | grep -iE 'state|runs|last exit'
```

### Revert an app
- nvim: set `M.base46.theme` back to `"onedark"` in `~/.config/nvim/lua/chadrc.lua`.
- fzf/p10k/syntax: comment the guarded `source`/`atload` lines in `.zshrc.local`.
- ghostty: comment the include in `~/.config/ghostty/config.local`.

---

## How it runs / survives restarts

- launchd agent `com.kmurthi.wallpaper-accent` auto-loads at login. `RunAtLoad`
  re-themes on login; `WatchPaths` fires on wallpaper change; `StartInterval 900`
  is a 15-min safety net (also catches light/dark flips).
- Not a daemon — runs on demand (~1–4s) and exits. An idempotency guard
  (`state.json`) skips work when nothing changed (`--force` overrides).
- All fragments persist on disk, so each app reads its last theme at startup.

---

## Caveats

- **Only image wallpapers work.** Dynamic/aerial/solid "Colors" wallpapers have
  no image file → the run logs `keeping previous theme` and exits 0.
- **fzf / p10k / syntax update new shells only** (per-process); nvim and ghostty
  update live.
- **Semantic + syntax hues are fixed**, never the accent.
- **nvim theme is switched to `wallpaper_accent`** (revert = one line in chadrc).
- `SIGUSR2` = ghostty reload, `SIGUSR1` = nvim. Any other signal crashes ghostty.
- `pgrep` is unreliable here; process detection uses `ps`.
- Hardcoded absolute paths (plist → `/opt/homebrew/bin/uv`, home dir). Update if
  you relocate things.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) to fix/extend or add another tool.
