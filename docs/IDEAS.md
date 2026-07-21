# wallpaper-accent — ideas backlog

Brainstormed extensions, to consider later. Grounded in the current
architecture (see [`ARCHITECTURE.md`](./ARCHITECTURE.md)): every new tool is a
**component** (`emit(pal)` [+ `reload()`]) picked from the **reload taxonomy**
(1 signal / 2 CLI / 3 re-read / 4 new-process), reading only from `pal` and
honoring **the invariant** — accent drives surfaces/borders/selection; semantic
+ syntax hues stay fixed.

Status legend: **[done]** shipped · **[next]** recommended · **[ ]** unscheduled.

---

## New tools to theme (new components)

Scored by reload class and the `pal` fields consumed. Prefer tools that (a) you
run daily, (b) reload live (class 1/2, so the effect is visible), and (c) have
real accent *surface area* (borders/selection/gradients) rather than mostly
semantic coloring (diff/ls), where the invariant pins most hues fixed.

### Tier 1 — high value, clean fit
- **[done] tmux** — class 2 (CLI, `tmux source-file`). Status bar, active pane
  border, current window, clock = accent; copy-mode = shared selection; message
  text neutral. Shipped this round.
- **[next] bat** — class 3 (re-reads each run). base16 → a `.tmTheme` in
  `~/.config/bat/themes/` + `bat cache --build` (do the rebuild in `reload()`).
- **[done] delta** (git pager) — class 3. `[delta]` gitconfig fragment `include`d
  from `~/.gitconfig`. +/- stay fixed green/red; file/line-number headers accent.
- **[ ] btop / htop** — class 2. Theme file; graph gradients are a natural home
  for the primary→secondary→tertiary spread (showcases the harmony).
- **[ ] starship** — class 4 (new shells). Alt prompt for non-p10k users.

### Tier 2 — good fit, mostly new-process / per-invocation
- **[done] lazygit** — class 3. `gui.theme`, base16 + accent on selected line / active border. Merged via `LG_CONFIG_FILE`.
- **[ ] eza / lsd** — class 4. `EZA_COLORS`/`LS_COLORS` env fragment; file-type hues stay fixed, accent only dir/selection.
- **[ ] k9s** — class 3. Skin YAML; base16 + accent on active/title.
- **[done] zsh-autosuggestions** — class 4. `ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE` = a grey from `pal["greys"]`. Trivial; complements zsh-syntax.
- **[done] yazi** (lf still [ ]) — class 3. Generated flavor (`flavors/wallpaper-accent.yazi/flavor.toml`); accent on cwd/cursor/selection.
- **[ ] glow / gh / ripgrep / fd / difftastic** — small env-fragment or config themes.

### Tier 3 — weaker fit (justify before building)
- **[ ] kitty / alacritty / wezterm** — only if actually run (ghostty covered). kitty is class 2 (`kitty @ set-colors`).
- **[ ] VS Code / Cursor** — own theme story, awkward live reload, GUI not terminal. Off-mission.
- **[ ] macOS accent / Terminal.app / Slack / Discord** — off-mission / TCC friction. No.

---

## Engine / core improvements

### Shipped this round
- **[done] Real CLI** — `theme` (default) / `show` / `doctor` / `components` /
  `preview` / `config` subcommands; bare-flag invocation still means `theme`
  (launchd unaffected). `theme --only NAME` themes a single component.
- **[done] Persistent knob config.** `config list/get/set/unset` writes
  `settings.json`; resolution is env var > settings file > default, so tuning no
  longer requires editing the launchd plist. Driven by one `config.KNOBS` registry.
- **[done] `doctor`** — verifies prereqs (`uv`), `colors.json`, launchd agent
  loaded, and every component's fragment + machine-local integration reference.
- **[done] Test suite** — `color.py` primitives, palette guards
  (`repel_accent`/`nudge_semantics`/`enforce_contrast`/`collision_report`), and
  an end-to-end `build_palette` invariant on a synthetic blue wallpaper.

### Palette / color quality
- **[next] Light-mode surfaces.** Verify/complete the light branch of
  `build_palette` (everything is tuned for dark; `BG_TONE 14`). Light-appearance
  flips should yield a genuinely light tinted surface, not an inverted dark one.
- **[done] Palette history + `--undo`.** `history.py` keeps a capped ring
  (`HISTORY_MAX`) of full past palettes in `last_palette.json`/`history.json`;
  `theme --undo` walks straight back through it (no oscillation on repeated
  undo), respects `--no-reload`.
- **[ ] Pin / lock a palette.** "I like this one" → freeze across wallpaper
  changes until unlocked (add a `pinned` flag that short-circuits idempotency).
- **[ ] `--strict` gate.** `collision_report` is diagnostic only; add a mode that
  fails (or rotates further) when any accent role is under the ΔE threshold.
- **[ ] Seed selection knob.** Expose "most-prominent" vs "most-saturated region"
  as an accent-source choice (partly in `_select_seed`).

### Robustness & observability
- **[done] Structured status / `--json`.** `doctor --json` and `components
  --json` emit machine-readable output for scripting/a future menubar UI.
- **[ ] More golden-palette fixtures.** Extend `test_palette.py` with greyscale,
  near-black, and monochromatic-scheme (`tonalspot` → `nudge_semantics`) cases.
- **[ ] Dynamic/"Colors" wallpapers.** Today: log + keep previous. Could derive
  the accent from the solid color / current dynamic frame instead of no-op.
- **[ ] Component self-description.** Let each `Component` declare its fragment +
  expected integration snippet, so `doctor` and docs generate from one source
  instead of the hand-maintained tables in `doctor.py` / `ARCHITECTURE.md`.

### CLI UX (this round)
- **[done] `--only`/`--skip` validate component names.** An unknown name is a
  hard FAIL listing known components (previously a silent empty-set no-op).
  Mutually exclusive with each other.
- **[done] `config set` numeric errors name the knob.** Wrapped instead of a
  raw `could not convert string to float: '...'`.
- **[done] `--version`.**
- **[done] `preview --dark/--light`** — was hardcoded to the live appearance.
- **[done] Shell completion.** `completion bash|zsh` prints a script (baked-in
  component/knob names); subcommands, `--only`/`--skip` components, `config`
  actions/knobs/schemes.

### Distribution
- **[done] De-hardcode paths / `install` command.** `wallpaper-accent install`
  templates the launchd plist from the actual `uv` path + repo checkout
  location (`agent.py`) and loads it; `uninstall` reverses it. `doctor` now
  points here instead of raw `launchctl` commands.
