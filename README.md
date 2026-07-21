# wallpaper-accent

Theme terminal tools from the macOS desktop wallpaper's accent color. When the
wallpaper changes, a background agent derives a Material You palette from the
image and re-themes **ghostty, fzf, powerlevel10k, fast-syntax-highlighting,
zsh-autosuggestions, neovim (NvChad), tmux, delta, lazygit, and yazi**,
hot-reloading whatever is running.

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
  wallpaper-accent.py                <- thin shim the launchd agent runs
  pyproject.toml  .python-version    <- deps + console entry
  README.md  ARCHITECTURE.md
  src/wallpaper_accent/              <- the engine (a Python package)
    config.py palette.py cli.py ...  <- core + shared helpers
    components/                      <- one module per tool (ghostty, fzf, ...)
~/.local/state/wallpaper-accent/     <- generated output (not in the repo)
  colors.json      <- shared palette (source of truth)
  ghostty.conf  fzf.env  p10k-accent.zsh  zsh-syntax.zsh  zsh-autosuggest.zsh
  tmux-accent.conf  delta.gitconfig  lazygit.yml
  state.json  run.log
~/.config/nvim/lua/themes/wallpaper_accent.lua       <- generated (must be in nvim rtp)
~/.config/yazi/flavors/wallpaper-accent.yazi/flavor.toml  <- generated yazi flavor
```

Architecture: one core extracts the accent → `colors.json`; each tool is a
**component** (`src/wallpaper_accent/components/<tool>.py`) that renders its
fragment and, if it can, reloads running instances. See
[`ARCHITECTURE.md`](./ARCHITECTURE.md) to add or extend one.

---

## Per-app behavior

| App | What follows the accent | Reload of running instances |
|---|---|---|
| **ghostty** | bg, fg, cursor, selection, greys, ANSI 1–15 (semantic hues fixed) | **live** — `SIGUSR2` |
| **nvim** (NvChad) | UI surfaces, statusline, popup, greys; syntax fixed | **live** — `SIGUSR1` autocmd |
| **fzf** | prompt/pointer/hl/bg+/border | new shells |
| **p10k** | directory path + prompt char | new shells |
| **fast-syntax-highlighting** | *not the accent* — a fixed, varied syntax theme (commands blue, builtins teal, strings green, comments grey, errors red) | new shells |
| **zsh-autosuggestions** | *not the accent* — a subdued tinted grey for the inline suggestion | new shells |
| **tmux** | status bar, active pane border, current window, clock; copy-mode selection | **live** — `tmux source-file` |
| **delta** (git pager) | file + hunk-header decorations, line-number gutter; +/- stay fixed red/green | re-read each invocation |
| **lazygit** | active border, options text, selected line, cherry-picked commits; unstaged changes fixed red | re-read each launch |
| **yazi** | cwd, mode, tabs, position indicator, file markers + selection; permission column fixed | re-read each launch |

Design rule: the accent drives **surfaces / greys / cursor / selection / accent-y
UI**; **semantic hues stay fixed** (Catppuccin red/green/yellow/blue/magenta/cyan
+ all code syntax) so logs, diffs, `ls`, and code stay legible under any wallpaper.
Distinct accent hues (primary/secondary/tertiary) are spread across roles so a
green wallpaper isn't uniformly green.

---

## How-to

The script is executable (its shebang runs `uv --system-certs`):

```bash
S=~/.config/wallpaper-accent/wallpaper-accent.py

# Re-theme everything from the current wallpaper:
$S --force                       # (bare flags == the `theme` subcommand)
$S theme --force

# Theme only one tool (repeatable):
$S theme --only ghostty --force

# Show the current palette as color swatches in the terminal:
$S show

# Preview any image WITHOUT writing anything (prints the palette JSON):
$S preview ~/Pictures/foo.png

# Check prerequisites + integration points are wired:
$S doctor

# List known / enabled components and their reload class:
$S components

# Apply a specific image / skip app reloads:
$S theme --image ~/Pictures/foo.png --force
$S theme --force --no-reload
```

> Subcommands: `theme` (default), `show`, `doctor`, `components`, `preview`,
> `config`. A
> bare-flag call (`… --force`) is treated as `theme --force`, so the launchd
> agent and shebang callers are unchanged.

### Diversify / tune the colors

Change these two ways — a **persistent CLI** (no plist edits) or one-off env
vars:

```bash
S=~/.config/wallpaper-accent/wallpaper-accent.py
$S config list                 # every knob, its value, and its source
$S config set bg_chroma 6      # persist an override (survives reboots + the agent)
$S config set scheme rainbow
$S config unset bg_chroma      # revert to default
$S theme --force               # apply now (else it applies on the next wallpaper change)
```

**Interactive (recommended):** `$S config edit` opens an arrow-key menu of every
knob. **↑/↓** select a knob, **←/→** change its value, **u** resets it to the
default, **q** quits. Each change is persisted to `settings.json` **and applied
live to ghostty** (the palette is rebuilt from the current wallpaper and a
running ghostty is reloaded via `SIGUSR2`), so you can dial in a look and watch
it update in real time. On quit, if you changed anything, it asks **`Apply theme
to all components now? [Y/n]`** — accept to re-theme the rest (fzf, p10k, nvim,
tmux) too, or decline and they pick the knobs up on the next `theme` run. Needs
an interactive terminal.

Overrides persist to `~/.local/state/wallpaper-accent/settings.json`. Precedence
is **env var > settings file > default**, so an env var still wins for a one-off.
Each `GHOSTTY_ACCENT_<X>` var below maps to the `config` knob `<x>` (e.g.
`GHOSTTY_ACCENT_BG_CHROMA` → `bg_chroma`, `GHOSTTY_ACCENT_MIN_HUE_SEP` → `min_hue_sep`).

**Harmony** — how varied the accent is (one wallpaper color → primary + secondary
+ tertiary). The scheme sets the base spread; `secondary_spread` then forces
secondary onto its own hue so the accent is three distinct colors, not two.

| Var | Default | Effect |
|---|---|---|
| `GHOSTTY_ACCENT_SCHEME` | `content` | `content` (wide, distinct hues), `vibrant`, `tonalspot` (monochromatic — one hue), `expressive`, `fruitsalad`, `rainbow` |
| `GHOSTTY_ACCENT_SECONDARY_SPREAD` | `40` | hue° to rotate secondary off primary for a genuinely tri-hue accent. `0` keeps the scheme's native (often 2-hue) spread. |

**Tint** — HCT: **tone** = lightness (0–100), **chroma** = colorfulness.

| Var | Default | Effect |
|---|---|---|
| `GHOSTTY_ACCENT_BG_CHROMA` | `22` | ↑ = more saturated background |
| `GHOSTTY_ACCENT_BG_TONE` | `14` | ↓ = darker background |
| `GHOSTTY_ACCENT_BLACK_CHROMA` | `18` | tint of ANSI "black" / darkest greys |
| `GHOSTTY_ACCENT_BLACK_TONE` | `22` | lightness of ANSI "black" |

**Guards** — keep the accent distinct from the fixed syntax hues, legible, and
alive even on adversarial wallpapers (e.g. a **blue** wallpaper vs syntax blue,
or a greyscale one). Sensible defaults; tune only if you want to.

| Var | Default | Effect |
|---|---|---|
| `GHOSTTY_ACCENT_MIN_HUE_SEP` | `20` | min hue° between accent and any syntax hue. Spread schemes rotate the accent off it; `tonalspot` nudges the syntax hue instead. `0` disables. |
| `GHOSTTY_ACCENT_CHROMA_FLOOR` | `12` | seeds duller than this are treated as near-greyscale → accent chroma is lifted so it stays vivid |
| `GHOSTTY_ACCENT_FALLBACK_HUE` | `210` | accent hue used when the wallpaper is essentially colourless (hue meaningless) |
| `GHOSTTY_ACCENT_FG_CONTRAST` | `4.5` | min WCAG contrast of foreground text over the tinted background |

One-off (this run only): `GHOSTTY_ACCENT_SCHEME=rainbow $S theme --force`
Persistent: `$S config set scheme rainbow` (or, equivalently, add under
`EnvironmentVariables` in the launchd plist and reload the agent — but `config`
is easier and needs no reload).

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

### Enable / disable a tool
Edit `DEFAULT_COMPONENTS` in `src/wallpaper_accent/config.py`, or for one run:
```bash
# only these:
WALLPAPER_ACCENT_COMPONENTS="ghostty,fzf" ~/.config/wallpaper-accent/wallpaper-accent.py --force
```
Known components: `ghostty, fzf, p10k, zsh-syntax, zsh-autosuggest, nvim, tmux,
delta, lazygit, yazi`. Adding a new one:
see [`ARCHITECTURE.md`](./ARCHITECTURE.md) ("Add a new tool").

### Revert an app
- nvim: set `M.base46.theme` back to `"onedark"` in `~/.config/nvim/lua/chadrc.lua`.
- fzf/p10k/syntax/autosuggest: comment the guarded `source`/`atload` lines in `.zshrc.local`.
- ghostty: comment the include in `~/.config/ghostty/config.local`.
- tmux: comment the guarded `source-file` line in `~/.tmux.conf`.
- delta: comment the `[include] path = …/delta.gitconfig` in `~/.config/git/config.local`.
- lazygit: drop `…/lazygit.yml` from `LG_CONFIG_FILE` in `.zshrc.local`.
- yazi: remove the `wallpaper-accent` flavor from `~/.config/yazi/theme.toml`'s `[flavor]`.

---

## Setup — run automatically on wallpaper change

The engine runs itself via a **launchd LaunchAgent**. `WatchPaths` watches the
macOS wallpaper store, so changing your desktop picture fires the script within
a second; `RunAtLoad` re-themes at login and `StartInterval` is a safety net.

**1. Prerequisite:** `uv` must be installed and allowlisted (`which uv` →
`/opt/homebrew/bin/uv` here). No other deps — `uv` provisions `materialyoucolor`
from the script's PEP-723 block on first run.

**2. Create the agent** at `~/Library/LaunchAgents/com.kmurthi.wallpaper-accent.plist`
(replace `kmurthi` / `/Users/kmurthi` with your username / `$HOME`, and the `uv`
path if `which uv` differs):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.kmurthi.wallpaper-accent</string>
  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/uv</string>
    <string>run</string><string>--system-certs</string>
    <string>--no-project</string><string>--script</string>
    <string>/Users/kmurthi/.config/wallpaper-accent/wallpaper-accent.py</string>
  </array>
  <key>RunAtLoad</key><true/>
  <!-- Fires when the desktop wallpaper changes (macOS rewrites this store). -->
  <key>WatchPaths</key>
  <array>
    <string>/Users/kmurthi/Library/Application Support/com.apple.wallpaper/Store</string>
    <string>/Users/kmurthi/Library/Application Support/com.apple.wallpaper/Store/Index.plist</string>
  </array>
  <!-- Safety net + catches light/dark flips (no file change). -->
  <key>StartInterval</key><integer>900</integer>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key><string>/Users/kmurthi</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <!-- Zscaler MITM: belt-and-suspenders with --system-certs. -->
    <key>SSL_CERT_FILE</key><string>/Users/kmurthi/.config/certs/zscaler-ca.user.pem</string>
    <!-- Optional: pin any GHOSTTY_ACCENT_* knob here, e.g.: -->
    <!-- <key>GHOSTTY_ACCENT_SCHEME</key><string>vibrant</string> -->
  </dict>
  <key>ProcessType</key><string>Background</string>
  <key>LimitLoadToSessionType</key><string>Aqua</string>
  <key>StandardOutPath</key><string>/Users/kmurthi/.local/state/wallpaper-accent/run.log</string>
  <key>StandardErrorPath</key><string>/Users/kmurthi/.local/state/wallpaper-accent/run.log</string>
</dict>
</plist>
```

**3. Load it** (and reload after any plist edit — see below):
```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.kmurthi.wallpaper-accent.plist
```

**4. Verify:** change your wallpaper, then check the log and palette:
```bash
tail -f ~/.local/state/wallpaper-accent/run.log      # should log a re-theme
~/.config/wallpaper-accent/wallpaper-accent.py --show # swatches for the new wall
launchctl print gui/$(id -u)/com.kmurthi.wallpaper-accent | grep -iE 'state|runs|last exit'
```

> Changing a `GHOSTTY_ACCENT_*` knob now re-themes on the **next** trigger even
> if the wallpaper is unchanged (the knobs are folded into the idempotency key),
> so you no longer need `--force` after editing the plist — just reload the agent.

---

## How it runs / survives restarts

- launchd agent `com.kmurthi.wallpaper-accent` auto-loads at login. `RunAtLoad`
  re-themes on login; `WatchPaths` fires on wallpaper change; `StartInterval 900`
  is a 15-min safety net (also catches light/dark flips).
- Not a daemon — runs on demand (~1–4s) and exits. An idempotency guard
  (`state.json`) skips work when nothing changed — the wallpaper, appearance,
  **and** the `GHOSTTY_ACCENT_*` knobs (`--force` overrides).
- All fragments persist on disk, so each app reads its last theme at startup.

---

## Caveats

- **Only image wallpapers work.** Dynamic/aerial/solid "Colors" wallpapers have
  no image file → the run logs `keeping previous theme` and exits 0.
- **fzf / p10k / syntax update new shells only** (per-process); nvim and ghostty
  update live.
- **Semantic + syntax hues are fixed**, never the accent. Guards keep the accent
  ≥`MIN_HUE_SEP`° off every syntax hue so a same-hued wallpaper (e.g. blue) can't
  make the cursor/prompt impersonate syntax blue; `--show`/`--print` report any
  residual collision. `tonalspot` is the one exception — it keeps the single-hue
  accent and instead nudges the colliding syntax hue.
- **nvim theme is switched to `wallpaper_accent`** (revert = one line in chadrc).
- `SIGUSR2` = ghostty reload, `SIGUSR1` = nvim. Any other signal crashes ghostty.
- `pgrep` is unreliable here; process detection uses `ps`.
- Hardcoded absolute paths (plist → `/opt/homebrew/bin/uv`, home dir). Update if
  you relocate things.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) to fix/extend or add another tool.
