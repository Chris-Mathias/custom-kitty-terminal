# English repo + settings menu — design

Date: 2026-11-11

## Intent

`custom-kitty-terminal` is the owner's kitty + Claude Code setup for Fedora/GNOME (tabs with Claude
session titles, session restore, stacked Claude sessions, a side panel mod, status lines, a Claude
theme and output style). Today everything — code, comments, file names, README, installer output and
every user-facing string — is in Brazilian Portuguese.

The owner wants:

1. **The repository itself in English**: code, identifiers, comments, file names, README, installer
   output, commit-facing docs.
2. **A settings menu** for the customizations, where they can pick the **language** of the
   user-facing text (Portuguese or English), the **theme**, the **font** and the **font size**.

Why: the owner wants the project presentable/shareable in English while still using it day to day in
Portuguese, and wants to change look-and-feel without hand-editing config files.

## Goals

- Every file in the repo is in English (identifiers, comments, file names, README, installer
  messages). The only Portuguese left in the repo is the Portuguese **translation strings** and the
  Portuguese output style / spinner verbs.
- One user setting, `language` (`en` | `pt`), switches **all** user-facing text the repo produces:
  - Claude spinner verbs (`spinnerVerbs` in `~/.claude/settings.json`);
  - Claude output style (`outputStyle`: "Concise English" vs "Português conciso");
  - side panel labels (SESSIONS/GIT/TASKS/FILES, "reading…", "nothing changed", toasts, the
    `/panel` command description and reply);
  - status line labels (e.g. `sem` → `wk`) and the weekday name of the weekly reset time;
  - subagent status line text (fallback name "agent", "N chg." suffix);
  - the close-tab / close-session confirmation dialog;
  - messages printed by `ct`, `claude-restore`, `claude-panel` and the settings menu itself.
- A **settings menu**, layout **B** (approved in the visual mockup): a list of items, each showing
  its current value; Enter opens a sub-list of choices for that item; Esc goes back; `q`/Esc at the
  top level closes. Items:
  - **Language**: English, Português.
  - **Theme**: Fedora, Catppuccin, Tokyo Night, Dracula, Gruvbox, Light.
  - **Font**: the monospace font families installed on the system (`fc-list :spacing=mono family`,
    de-duplicated, sorted).
  - **Font size**: integer steps (sensible range, e.g. 8–24).
- The menu opens from:
  - the command **`ct config`**;
  - a **⚙ button at the right end of the kitty tab bar** (directly under the GNOME close button);
  - a keyboard shortcut (see "Builder's calls").
  Inside kitty it opens as an overlay on the current tab; outside kitty it runs inline in the
  current terminal.
- **A theme switch changes kitty and Claude together, at once**: kitty colors (including the tab
  bar), the Claude Code theme, the status line / subagent line / panel / dialog accent colors.
- Changes apply immediately in kitty (all running kitty instances reload). Claude Code picks them up
  live if it hot-reloads `settings.json`; otherwise the menu says the change applies to new Claude
  sessions (the builder verifies which, see "Open technical points").
- **Fresh installs start in English** with the Fedora theme, Adwaita Mono 12. The installer does not
  ask anything.
- The owner's current machine is migrated cleanly from the Portuguese install (see "Migration").

## Non-goals

- No languages beyond `en` and `pt`.
- No settings for keyboard shortcuts, tab bar style, status line contents, or panel sections in this
  round (the menu should be easy to extend later, but no extra items now).
- No changes to things outside this repo's own files (other Claude plugins, the rest of
  `settings.json`, GNOME settings).
- Translating Claude's own UI (Claude Code's built-in text) is out of scope; only what this repo
  produces.

## Anti-goals (would make this a failure even if it "works")

- `git pull` overwriting or conflicting with the user's choices: user settings must live outside the
  repo, and no repo-tracked file may be edited by the menu.
- The tab bar breaking (or kitty failing to start) after a kitty update because of the ⚙ button.
  The button is a nice-to-have; tabs must keep working if it can't be installed.
- The migration leaving dangling symlinks, stale `.bak` clutter in active paths, a broken
  `~/.zshrc` `claude` function, or a saved session file that calls scripts that no longer exist.
- Clobbering unrelated keys in `~/.claude/settings.json` (the user has `model`, `enabledPlugins`,
  `autoMode`, etc.).
- Mixed-language output: e.g. English panel with Portuguese toasts.

## Constraints and context

- Platform: Fedora 44, GNOME, kitty 0.47.1 running under XWayland (`linux_display_server x11`), zsh,
  Claude Code ≥ 2.1.287 (the panel mod API). `jq`, `git`, `python3` available.
- Install model stays the same: `install.sh` symlinks repo files into place so `git pull` updates
  everything; pre-existing non-repo files are moved aside as `.bak-<date>`; Claude `settings.json`
  is merged, never replaced.
- The owner launches Claude by typing `claude`; `~/.zshrc` has a `claude()` function adding
  `--plugin-dir ~/.local/share/claude-mods/painel-sessao`. That path changes with the rename, so
  this function must be updated (installer should own it — see Migration).
- kitty's tab bar has no native "custom button" support. Clicks on the tab bar are dispatched by
  `TabManager.handle_tab_bar_mouse` (kitty/tabs.py) using tab extents; the only synthetic button is
  the `+` new-tab button (negative tab id). A ⚙ button therefore needs either a supported hook or a
  guarded monkeypatch from the custom `tab_bar.py` (loaded inside the kitty process when
  `tab_bar_style custom`).
- Current look must be preserved when the Fedora theme + English/Portuguese is selected: slanted
  powerline tabs, `+` button, GNOME palette, same status line layout.

## Decided by the owner

- Repo fully in English, including file names.
- Language choice: Portuguese or English; affects everything user-facing listed above, including
  Claude's output style.
- Menu entry points: `ct config` and a ⚙ in the tab bar's right corner.
- Menu layout: **B — list with sub-menus**.
- Menu items: language, theme, font, font size.
- Themes: Fedora, Catppuccin, Tokyo Night, Dracula, Gruvbox, and a light one.
- A theme changes kitty and Claude **together, at once**.
- New installs start in **English**.

## Builder's calls (made by Claude during design — owner may override)

- **File renames** (Portuguese → English):
  | Old | New |
  |---|---|
  | `kitty/abas.conf` | `kitty/tabs.conf` |
  | `kitty/fechar_aba.py` | `kitty/close_tab.py` |
  | `kitty/fechar-aba-dialogo.sh` | `kitty/close-tab-dialog.sh` |
  | `kitty/salvar_sessao.py` | `kitty/save_session.py` |
  | `~/.config/kitty/ultima-sessao.kitty-session` | `~/.config/kitty/last-session.kitty-session` |
  | `bin/claude-painel` | `bin/claude-panel` |
  | `bin/claude-restaurar` | `bin/claude-restore` |
  | `claude/painel-sessao/` | `claude/session-panel/` (plugin name `session-panel`, command `/panel`) |
  | `claude/output-styles/portugues-conciso.md` | stays as a translation: `claude/output-styles/portugues-conciso.md` + new `claude/output-styles/concise-english.md` |
  | `~/.local/share/claude-mods/painel-sessao` | `~/.local/share/claude-mods/session-panel` |
  | `CLAUDE_PAINEL_DIR` env var | `CLAUDE_PANEL_DIR` |
  | kitten arg `janela` | `window` |
  `ct` keeps its name.
- **User settings file**: `~/.config/custom-kitty-terminal/settings.json`
  (`{"language":"en","theme":"fedora","font_family":"Adwaita Mono","font_size":12}`), created with
  defaults by `install.sh` if missing, never overwritten by it.
- **Single source of translations**: `i18n/en.json` and `i18n/pt.json` (flat key → string), read by
  every component (bash via `jq`, Python via `json`, the panel via `$.fs`). Spinner verbs live there
  too (array value).
- **Themes as data**: `themes/<id>/` with `kitty.conf` (colors + tab bar colors), `claude.json`
  (Claude custom theme, installed as `~/.claude/themes/<id>.json` → `custom:<id>`), and
  `palette.json` (accent/green/yellow/red/etc. for status lines, panel, dialog). Theme ids:
  `fedora`, `catppuccin` (Mocha), `tokyo-night` (Night), `dracula`, `gruvbox` (Dark),
  `light` (GNOME/Adwaita light palette, Claude `base: "light"`). Palettes taken from each project's
  official published colors.
- **Applying settings** (one `apply` step, used by the menu and by `install.sh`):
  - writes generated, non-tracked kitty includes in `~/.config/kitty/generated/`
    (`theme.conf`, `font.conf`), which the repo's `kitty.conf` `include`s — so `kitty.conf` stays a
    symlink and has no user values;
  - reloads every running kitty (`SIGUSR1` to kitty processes of the user, or `kitten @ load-config`
    per socket);
  - merges into `~/.claude/settings.json` only `theme`, `outputStyle`, `spinnerVerbs` (and keeps
    `statusLine`/`subagentStatusLine` as today), via `jq`, atomically.
- **Menu implementation**: `python3` + `curses` script `bin/ct-config` (called by `ct config`),
  Fedora-friendly, no extra deps. Colors follow the active theme's palette. The menu shows a short
  line after a change ("Applied." / "Applies to new Claude sessions." as appropriate), translated.
- **⚙ button**: switch `tabs.conf` to `tab_bar_style custom`; `kitty/tab_bar.py` reproduces today's
  slanted powerline look by delegating to kitty's own `draw_tab_with_powerline`, and draws ⚙
  right-aligned after the last tab. Clicks: at import, `tab_bar.py` wraps
  `TabManager.handle_tab_bar_mouse` to detect a single left click within the ⚙ cell range and launch
  `ct-config` as an overlay; everything else goes to the original handler. The wrap is inside
  `try/except` and checks the attribute exists — on failure, no ⚙ is drawn and tabs work normally.
  The builder must spike this first; if it can't be made reliable, drop the ⚙ and keep shortcut +
  `ct config`, and report it.
- **Keyboard shortcut**: `ctrl+shift+f2` (kitty's default "edit config" key) opens the menu.
- **Owner's machine** gets `language: "pt"` during migration, since that's what they use today
  (fresh installs elsewhere default to `en`).
- **`ct config` vs a folder named `config`**: `ct config` is the menu; to open Claude in a folder
  literally named `config`, use `ct ./config`. Documented in `ct --help` and README.
- **README** in English, with a short note that the UI can be switched to Portuguese via `ct config`.

## Migration (owner's existing Portuguese install)

`install.sh` must handle a machine that already ran the old Portuguese installer:

- Remove old symlinks that point into this repo under their old names (`abas.conf`, `fechar_aba.py`,
  `fechar-aba-dialogo.sh`, `salvar_sessao.py`, `claude-painel`, `claude-restaurar`,
  `claude-mods/painel-sessao`) — only if they are symlinks into this repo; anything else is left and
  reported.
- Rename `ultima-sessao.kitty-session` → `last-session.kitty-session`, rewriting
  `claude-restaurar` → `claude-restore` inside it, so the next kitty start still restores tabs.
- `~/.claude/output-styles/portugues-conciso.md` and `~/.claude/themes/fedora.json` symlinks are
  re-pointed as needed.
- The `claude()` function in `~/.zshrc`: the installer owns a clearly delimited block
  (`# >>> custom-kitty-terminal >>>` … `# <<< custom-kitty-terminal <<<`) containing the function
  pointing at `session-panel`; it replaces the manually-added function on this machine (the
  current one sits right after the NVM lines, commented `# Claude Code com o painel lateral
  (custom-kitty-terminal)`), and on re-runs only rewrites its own block.
- Writes the user settings file if missing (owner's machine: `language: "pt"` — the installer can
  detect the old install, e.g. `outputStyle == "Português conciso"` in Claude settings, and seed
  `pt`; otherwise `en`).
- Re-running `install.sh` is idempotent.
- **Running under a live kitty** (builder's call): the installer migrates immediately and does not
  refuse to run inside kitty. The old `salvar_sessao.py` watcher stays loaded in the running kitty
  and may keep rewriting `ultima-sessao.kitty-session`; so the installer ends by telling the user to
  restart kitty, and the new `save_session.py` (and every later `install.sh` run) converts and removes a
  leftover `ultima-sessao.kitty-session` if one shows up again. Claude sessions that are already
  running keep the panel they loaded; new ones use `session-panel`. No shims are kept under the
  Portuguese names.
- **Backups** (builder's call): `settings.json` is backed up as `.bak-<date>` only when the merge
  actually changes it; the menu's apply step writes atomically with no backup.

## Git (decided by the owner / builder's call)

- Owner: small commits, Conventional Commits, short descriptive messages, **no co-author trailer**.
- Builder's call: work on a branch (`feat/english-and-settings-menu`) off `main`; no history rewrite,
  no push (owner pushes/merges). The owner's pending working-tree changes (`font_size` 13→12 and
  `.gitignore` adding `.superpowers/`) go in as their own first commits. Renames use `git mv`.

## Open technical points (builder verifies, reports outcome)

1. Whether Claude Code hot-reloads `theme`, `outputStyle` and `spinnerVerbs` from `settings.json`
   in running sessions. Menu message depends on it.
2. How the panel mod reads the user settings file and refreshes labels when the language changes
   (re-read on render or on a clock; must not hurt performance).
3. The ⚙ monkeypatch spike (above).

## Verification expected

- Existing panel test (`claude/painel-sessao/tests/painel.test.tsx`) moved/updated and passing;
  new tests for i18n lookup where cheap.
- `kitty --debug-config` clean for every theme × font combination tried.
- Manual check in kitty: switch language/theme/font/size from the menu and see kitty, status line,
  panel and close dialog change; tab restore still works after migration; `claude` from zsh still
  loads the panel.
- `grep` for Portuguese words across non-translation files returns nothing meaningful.
