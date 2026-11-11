# More settings — design

Date: 2026-11-11
Builds on: `2026-11-11-english-repo-and-settings-menu-design.md` (settings file, i18n, themes, apply step, curses menu, ⚙ button).

## Intent

The owner wants the setup "very customizable" before sharing it: most look-and-feel and behavior choices, every project shortcut, and Claude's response style should be changeable from the settings menu, without hand-editing config files.

## Goals

1. **Grouped menu (layout A, approved in mockup).** Top level: **Appearance**, **Claude Code**, **Behavior**, **Shortcuts**, **Language**. Enter on a group opens its item list (each row shows the current value); Enter on an item opens its choices (as today); Esc goes back one level; `q` quits. Language stays a direct item at the top.
2. **Appearance:** theme, font, font size (existing) plus:
   - line height: 100–130 % in steps of 5 (default 115);
   - padding: compact / normal / roomy (default normal = today's `4 8`);
   - tab style: slanted (default), round, angled, separators;
   - tab bar position: top (default) / bottom;
   - transparency: 100 % (default) down to 70 % in steps of 5 (no blur option: kitty's blur doesn't work on GNOME);
   - cursor shape: block (default) / beam / underline; cursor blink on (default) / off;
   - title bar: GNOME (default, today's XWayland setup) / kitty's own / none;
   - ligatures: on (default) / off.
3. **Claude Code:**
   - **Response style — OFF by default ("Claude's default").** While off, the project never writes `outputStyle` and never installs a style file. When the user turns it on they pick the **response language** (Portuguese / English) and **length** (short / balanced / detailed). The project then writes ONE generated style file and sets `outputStyle` to its name. Turning it back off deletes that file and removes `outputStyle` only if it still equals the project's style name.
   - **Status line items:** individually on/off: context, 5h limit, weekly limit, reset times, model, worktree (all on by default).
   - **Side panel:** which sections show (sessions, git, tasks, files — all on by default), their order (default: that order), and whether it opens automatically when a session starts (default on).
   - **Spinner phrases:** ours in the chosen language (default) / Claude's defaults (project removes `spinnerVerbs` only if it equals what the project wrote).
4. **Behavior:**
   - reopen tabs on start: on (default) / off;
   - confirm before closing: only when something runs (default) / always / never;
   - kitty takes `Ctrl+W` / `Ctrl+N`: on (default) / off (then they reach the shell and Claude);
   - scrollback size: 5 000 / 10 000 / 20 000 (default) / 50 000 / 100 000 lines;
   - bell: off (default) / on.
5. **Shortcuts:** every shortcut the project defines (the table in README: new Claude tab, new stacked session, previous/next session, toggle stack, close session, close tab, new tab (`Ctrl+N`, `Alt+T`, `Ctrl+Shift+T`), go to tab 1–6, previous/next tab, split right/below, settings menu). Each row shows its current combination. Enter → "press the new combination" screen: the user presses the keys and the menu records them. While capturing, kitty's own shortcuts are suspended so the combination reaches the menu, then restored. If the combination is already used by another project shortcut, the menu says which and asks to confirm (swap) or cancel. Each shortcut has "reset to default"; the group has "reset all".
6. **Defaults reproduce today's behavior exactly** — an existing user who upgrades sees nothing change (except the response style, already off).
7. Everything user-facing in en/pt via i18n, as today.

## Non-goals

- Shortcuts kitty defines by itself (copy/paste, font size, etc.) aren't customizable here.
- No per-theme overrides, no custom color editor, no arbitrary font-size/padding numbers outside the listed choices.
- No new languages.

## Anti-goals

- Touching Claude's `outputStyle`, output-style files or `spinnerVerbs` for a user who didn't opt in, or removing values the user set themselves.
- Leaving kitty with shortcuts disabled if the menu crashes or is closed mid-capture.
- A settings change that leaves kitty's config invalid (kitty must always start).
- Breaking the existing settings file: older files (four keys) must load with defaults for everything new.
- Mixed-language text.

## Constraints

- Same architecture: user choices in `~/.config/custom-kitty-terminal/settings.json`; `apply()` regenerates files under `~/.config/kitty/generated/` and merges owned keys into `~/.claude/settings.json`; repo files are never edited at runtime.
- kitty 0.47.1 on GNOME/XWayland; Claude Code ≥ 2.1.287; bash + jq, python3 stdlib, curses.
- The status line scripts and the panel already read the settings file; new options extend that.
- kitty intercepts mapped shortcuts before the overlay program sees them; the menu runs as a kitty overlay (or inline via `ct config`).

## Builder's calls (Claude's, owner may override)

- **Settings file shape:** keep the flat keys that exist; add nested objects for groups with many flags: `"status_line": {"context": true, ...}`, `"panel": {"sections": ["sessions","git","tasks","files"], "auto_open": true}`, `"response_style": {"enabled": false, "language": "pt", "length": "short"}`, `"shortcuts": {"<action id>": "ctrl+alt+t", ...}` (only overrides stored; missing = default). Validation per key falls back to defaults like today.
- **kitty side:** `apply()` writes `generated/appearance.conf`, `generated/behavior.conf`, `generated/shortcuts.conf`; `kitty.conf` keeps only fixed settings and `include`s them. All `map` lines move out of `kitty.conf` into the generated `shortcuts.conf`, built from a table of actions (id, default keys, kitty action, i18n label) in `lib/shortcuts.py`. "Kitty takes Ctrl+W/Ctrl+N" off simply omits those maps.
- **Title bar:** GNOME = today (`linux_display_server x11`, decorations on); kitty's own = `linux_display_server auto`, decorations on; none = `hide_window_decorations yes`. `linux_display_server` needs a kitty restart: the menu says so for that item.
- **Reopen tabs off:** `startup_session none` and no watcher line; the saved file is kept.
- **Confirm before closing:** passed to `close_tab.py` through the settings file ("always" asks even when idle; "never" closes right away).
- **Tab styles:** slanted/round/angled map to kitty's powerline styles; "separators" uses kitty's separator style through our `tab_bar.py` (which must keep the ⚙ for every style). Bottom position flips `tab_bar_edge`.
- **Response style file:** `~/.claude/output-styles/custom-kitty-terminal.md` (regular file, generated from i18n text per language × length), name `"Terminal: <Language>, <length>"` style e.g. "Terminal — Português, curto". `keep-coding-instructions: true`.
- **Key capture:** the menu switches to raw input and enables the kitty keyboard protocol (`CSI > 1 u` / report all keys) to read modifiers reliably, converts to kitty's `ctrl+alt+x` notation, and restores on exit (also in a `finally`/signal handler). Suspension of kitty shortcuts: `kitten @ load-config` with an override `clear_all_shortcuts yes` (or `action` that pushes a keyboard mode with no maps), restored right after; the builder spikes the mechanism first and records which works. If neither works, capture still works for combinations kitty doesn't use, and the menu shows a note.
- **Live reload:** all kitty changes go through the existing SIGUSR1 reload; status line and panel re-read settings as today.

## Calls settled after the builder check (Claude's, owner may override)

- **A response style the user already had:** turning ours on saves their current `outputStyle` value in our settings file; turning ours off puts it back (or removes the key if there was none). Never lost.
- **One row per key combination:** every `map` line is its own row. "New tab" becomes three rows (Ctrl+N, Alt+T, Ctrl+Shift+T labelled "New tab", "New tab (2)", "New tab (3)"); "Go to tab 1…6" are six rows. Stored as `"shortcuts": {"<id>": "<keys>"}`; swap and reset work per row.
- **"kitty takes Ctrl+W / Ctrl+N" is about the keys:** when off, no project shortcut is mapped to `ctrl+w` or `ctrl+n` (rows still on those keys show "off — given to the shell"), and capture refuses those two keys with a note.
- **A key the project stops using** goes back to kitty's own default (no `no_op`). **Picking a combination kitty uses by itself** (e.g. `ctrl+shift+c`): the menu warns with kitty's action name and asks to confirm; the list comes from kitty's default keymap at runtime.
- **Upgrading:** like last round, `git pull` must be followed by `./install.sh` (README says so). `kitty.conf` keeps only what doesn't depend on settings.

## Open technical points (builder verifies)

1. Reliable way to suspend kitty shortcuts during capture and guarantee restore.
2. Whether `background_opacity` changes apply on reload (kitty requires `dynamic_background_opacity` for live changes; otherwise note "after restart").
3. That every tab style still leaves room for and draws the ⚙.

## Verification

- Unit tests for settings validation (old file → defaults), generated kitty files per option, Claude merge rules (opt-in / opt-out / user-owned values preserved), shortcut table → `map` lines, key-event → notation parsing, menu state machine for groups and capture flow.
- kitty's `load_config` reports 0 bad lines for every option value.
- Manual: owner tries each group in kitty.
