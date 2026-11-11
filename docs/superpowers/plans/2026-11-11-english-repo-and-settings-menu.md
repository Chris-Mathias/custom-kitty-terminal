# English Repo + Settings Menu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the whole repo English, add `en`/`pt` user-facing text, six themes, font settings, and a settings menu opened by `ct config`, `ctrl+shift+f2` and a ⚙ in the kitty tab bar.

**Architecture:** User choices live in `~/.config/custom-kitty-terminal/settings.json`. A Python library (`lib/ckt.py`) loads settings, translations (`i18n/*.json`) and theme data (`themes/<id>/`), and *applies* them (generated kitty includes + a minimal merge into `~/.claude/settings.json` + kitty reload). Bash components read the same files through `lib/ckt.sh` (jq); the panel mod reads them with `$.fs.read`. A curses menu (`bin/ct-config`) edits settings and calls apply.

**Tech Stack:** bash + jq, python3 (stdlib only: json, curses, unittest), kitty 0.47 config/kittens/watchers, Claude Code mod API (TSX, `claude plugin test`).

**Spec:** `docs/superpowers/specs/2026-11-11-english-repo-and-settings-menu-design.md`

## Global Constraints

- Every non-translation file in English (identifiers, comments, file names, messages). Portuguese only in `i18n/pt.json` and `claude/output-styles/portugues-conciso.md`.
- Languages: `en`, `pt`. Defaults for fresh install: `{"language":"en","theme":"fedora","font_family":"Adwaita Mono","font_size":12}`.
- Theme ids: `fedora`, `catppuccin` (Mocha), `tokyo-night` (Night), `dracula`, `gruvbox` (Dark), `light` (GNOME light, Claude `base: "light"`).
- Font size range 8–24, step 1. Font list: `fc-list :spacing=mono family`, first family name per line, de-duplicated, sorted.
- Settings dir override for tests: env `CKT_CONFIG_DIR` (default `~/.config/custom-kitty-terminal`). All home paths derive from `$HOME` so tests run with `HOME=<tmp>`.
- Never edit repo-tracked files at runtime. Generated kitty files go to `~/.config/kitty/generated/{theme.conf,font.conf}`.
- `~/.claude/settings.json` merge touches only `theme`, `outputStyle`, `spinnerVerbs`, `statusLine`, `subagentStatusLine`; atomic write (tmp + rename); unrelated keys preserved byte-for-byte in value.
- Renames per the spec table; use `git mv`.
- Commits: small, Conventional Commits, short messages, **no co-author/attribution trailer**. Branch `feat/english-and-settings-menu`, no push.
- Python tests: `python3 -m unittest discover -s tests -v` from repo root. Panel tests: `claude plugin test claude/session-panel`.

## Review Focus

- Missing/corrupt `~/.config/custom-kitty-terminal/settings.json` (or unknown theme/language value): every component must fall back to defaults, never crash or print raw keys.
- A translation key missing in `pt.json`: lookup falls back to `en`, then to the key itself.
- `~/.claude/settings.json` absent, empty, or invalid JSON: apply must not destroy it — create when absent; when invalid, leave it untouched and report an error.
- Font family names with spaces (`Adwaita Mono`, `JetBrains Mono`) round-trip into kitty's `font_family` unquoted and correctly.
- Re-running `install.sh` (twice in a row, and on the old Portuguese layout) leaves no dangling symlinks and exactly one `custom-kitty-terminal` block in `~/.zshrc`.

---

### Task 0: Branch and owner's pending changes

- [ ] **Step 1:** `git switch -c feat/english-and-settings-menu`
- [ ] **Step 2:** Commit owner's changes separately:
  - `git add kitty/kitty.conf && git commit -m "chore(kitty): set font size to 12"`
  - `git add .gitignore && git commit -m "chore: ignore .superpowers brainstorm files"`
  - `git add docs && git commit -m "docs: add design and plan for English repo and settings menu"`

### Task 1: Rename and translate the repo (no behavior change)

Pure translation: file names, identifiers, comments, README stays for Task 9. User-facing strings stay Portuguese for now (they move to i18n in Tasks 3–4), so behavior is unchanged.

**Files:**
- `git mv` per spec table: `kitty/abas.conf→kitty/tabs.conf`, `kitty/fechar_aba.py→kitty/close_tab.py`, `kitty/fechar-aba-dialogo.sh→kitty/close-tab-dialog.sh`, `kitty/salvar_sessao.py→kitty/save_session.py`, `bin/claude-painel→bin/claude-panel`, `bin/claude-restaurar→bin/claude-restore`, `claude/painel-sessao→claude/session-panel`, `claude/painel-sessao/tests/painel.test.tsx→claude/session-panel/tests/panel.test.tsx`.
- Modify all of them plus `kitty/kitty.conf`, `kitty/tab_bar.py`, `bin/ct`, `claude/statusline.sh`, `claude/subagent-statusline.sh`, `.gitignore`.

**Interfaces (Produces):**
- kitty session file name `last-session.kitty-session`; kitten arg `window` (was `janela`); dialog target prefixes `tab:<id>` / `window:<id>`.
- Plugin name/state key/pane id `session-panel`; slash command `/panel`; `TouchKind = 'read' | 'edited' | 'created'`.
- `CLAUDE_PANEL_DIR` env var; panel path `~/.local/share/claude-mods/session-panel`; `ct -a|--here`.

- [ ] **Step 1:** Do the renames and update every internal reference (`grep -rn "painel\|restaurar\|fechar\|salvar\|abas\|ultima-sessao\|janela"` must only hit user-facing Portuguese strings afterwards).
- [ ] **Step 2:** Translate identifiers and comments to English in all files listed. Update the panel test to new names (`plugin: 'session-panel'`, `command: 'panel'`), keeping its assertions on the Portuguese labels for now.
- [ ] **Step 3:** Verify: `claude plugin test claude/session-panel` → `1 pass`; `bash -n` on every `.sh`/bin script; `python3 -m py_compile kitty/*.py`.
- [ ] **Step 4:** Commit in two steps: `refactor: rename files and paths to English` (renames + reference updates) then `refactor: translate code and comments to English`.

### Task 2: Settings, translations and theme data library

**Files:**
- Create: `lib/ckt.py`, `lib/ckt.sh`, `i18n/en.json`, `i18n/pt.json`, `themes/<id>/{kitty.conf,claude.json,palette.json}` ×6, `claude/output-styles/concise-english.md`
- Move: `claude/themes/fedora.json → themes/fedora/claude.json` (`git mv`; its `name` stays "Fedora")
- Test: `tests/test_ckt.py`

**Interfaces (Produces) — `lib/ckt.py`:**
- `REPO: Path` (resolved via `Path(__file__).resolve().parent.parent`)
- `DEFAULTS: dict` (Global Constraints values); `LANGUAGES = ("en", "pt")`; `THEMES = ("fedora","catppuccin","tokyo-night","dracula","gruvbox","light")`
- `config_dir() -> Path` (honors `CKT_CONFIG_DIR`); `settings_path() -> Path`
- `load_settings() -> dict` — defaults merged with file; invalid values per key replaced by default; missing/corrupt file → defaults.
- `save_settings(s: dict) -> None` — atomic write.
- `t(key: str, lang: str | None = None) -> str | list` — lookup in `i18n/<lang>.json`, fallback `en`, then `key`.
- `palette(theme: str) -> dict[str, str]` — keys: `accent`, `accent_bg`, `fg`, `bg`, `dim`, `surface`, `green`, `yellow`, `red`, `magenta`, `cyan`, `orange` (hex `#rrggbb`).
- `theme_label(theme) -> str` (from `claude.json` `name`).
- `mono_fonts() -> list[str]`.

**`lib/ckt.sh`** (sourced by bash scripts; resolves repo via `readlink -f "${BASH_SOURCE[0]}"`): `ckt_lang`, `ckt_theme`, `ckt_t <key>`, `ckt_color <palette-key>` (prints `\e[38;2;r;g;bm`), `ckt_bg <palette-key>`. Missing settings/keys fall back like the Python side.

**i18n keys** (flat, dotted): `spinner.verbs` (array; en list = English equivalents of today's 14 pt verbs), `output_style` (`"Concise English"` / `"Português conciso"`), `panel.*`, `status.*`, `subagent.*`, `dialog.*`, `cli.*`, `menu.*`. Tasks 3–6 add the keys they use; keep `en.json` and `pt.json` key sets identical (test enforces).

- [ ] **Step 1: Write failing tests** in `tests/test_ckt.py` (each sets `CKT_CONFIG_DIR` to a temp dir):
  - `test_defaults_when_missing`: `load_settings() == DEFAULTS`
  - `test_corrupt_file_gives_defaults`: file `"{nope"` → `DEFAULTS`
  - `test_invalid_values_replaced`: `{"language":"fr","theme":"x","font_size":99}` → those three keys equal defaults
  - `test_save_roundtrip`
  - `test_t_falls_back_to_en_then_key`: with a temp key only in en; and `t("no.such.key","pt") == "no.such.key"`
  - `test_i18n_key_sets_match`: `set(en) == set(pt)`
  - `test_every_theme_complete`: for each id, `palette()` has all 12 keys as `#rrggbb`, `themes/<id>/kitty.conf` defines `foreground`, `background`, `color0..color15`, `active_tab_background`, `inactive_tab_background`, `tab_bar_background`; `claude.json` has `name`, `base`, `overrides`.
  - `test_shell_lookup_matches_python`: `bash -c 'source lib/ckt.sh; ckt_t output_style'` equals `t("output_style")` for both languages.
- [ ] **Step 2:** Run `python3 -m unittest tests.test_ckt -v` → FAIL (module missing).
- [ ] **Step 3:** Implement `lib/ckt.py`, `lib/ckt.sh`, i18n files (seed `spinner.verbs`, `output_style`), theme dirs. Fedora values come from today's `kitty.conf` colors + `tabs.conf` tab colors + statusline colors; others from each project's official palette. `concise-english.md` mirrors `portugues-conciso.md` (front-matter `name: Concise English`, English instructions, "always answer in English").
- [ ] **Step 4:** Tests PASS.
- [ ] **Step 5:** Commit: `feat: add settings, i18n and theme data library` (+ separate `feat(themes): add catppuccin, tokyo night, dracula, gruvbox and light` if the diff is large).

### Task 3: Apply settings (kitty + Claude)

**Files:** Modify `lib/ckt.py`, `kitty/kitty.conf`, `kitty/tabs.conf`; Create `bin/ckt-apply`; Test `tests/test_apply.py`

**Interfaces (Produces):**
- `apply(s: dict | None = None, reload: bool = True) -> list[str]` — returns list of human messages (translated) for problems; writes `~/.config/kitty/generated/theme.conf` (copy of `themes/<theme>/kitty.conf`) and `font.conf` (`font_family <name>` / `font_size <n>.0`); merges Claude settings; reloads kitty if `reload`.
- `merge_claude_settings(s: dict) -> bool` — returns False (and leaves the file untouched) when existing file is invalid JSON; creates it when absent. Sets `theme: "custom:<id>"`, `outputStyle: t("output_style")`, `spinnerVerbs: {"mode":"replace","verbs": t("spinner.verbs")}`, `statusLine`, `subagentStatusLine` (same values as today's `claude/settings.json`).
- `reload_kitty() -> None` — `pkill -USR1 -u $USER -x kitty`, ignore failures.
- `bin/ckt-apply`: CLI wrapper, `--no-reload` flag; exit 1 when `apply` returned messages.
- `kitty/kitty.conf`: remove font + color blocks, add `include generated/theme.conf` and `include generated/font.conf` (keep `modify_font cell_height 115%` and all non-color settings). `tabs.conf`: drop color lines (now in theme).
- Delete `claude/settings.json` (its content now produced by `merge_claude_settings`).

- [ ] **Step 1: Failing tests** (`HOME` and `CKT_CONFIG_DIR` → temp dirs, `reload=False`):
  - `test_generates_kitty_includes`: font `"JetBrains Mono"`, size 14 → `font.conf` contains `font_family JetBrains Mono` and `font_size 14.0`; `theme.conf` equals `themes/dracula/kitty.conf`.
  - `test_merge_preserves_other_keys`: existing `{"model":"opus","enabledPlugins":{"a":true},"theme":"dark"}` → after apply `model`/`enabledPlugins` unchanged, `theme == "custom:dracula"`, `outputStyle == "Português conciso"` for pt.
  - `test_merge_creates_when_absent`
  - `test_invalid_claude_settings_left_untouched`: content `"{bad"` stays identical, `apply` returns one message.
  - `test_language_switch_changes_verbs`: en → verbs equal `t("spinner.verbs","en")`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Tests PASS; `kitty --debug-config` with real HOME after `bin/ckt-apply --no-reload` shows no errors, and for each theme × (`Adwaita Mono`, a second installed mono font) loop the same.
- [ ] **Step 5:** Check hot-reload: with a running Claude session, change `theme`/`outputStyle`/`spinnerVerbs` via `bin/ckt-apply`; record in the commit body / final report whether running sessions pick each up. Add i18n key `menu.applied_claude_new_sessions` used by the menu if not live.
- [ ] **Step 6:** Commit: `feat: apply settings to kitty and Claude Code`.

### Task 4: Translate shell components

**Files:** Modify `claude/statusline.sh`, `claude/subagent-statusline.sh`, `kitty/close-tab-dialog.sh`, `kitty/close_tab.py`, `bin/ct`, `bin/claude-restore`, `bin/claude-panel`; extend `i18n/*.json`; Test `tests/test_shell_i18n.py`

**Interfaces (Consumes):** `lib/ckt.sh` (`ckt_t`, `ckt_color`, `ckt_bg`); `lib/ckt.py` `t` from `close_tab.py` (insert repo `lib` into `sys.path` via `os.path.realpath` of `config_dir/close_tab.py`).

- Status line: weekly label key `status.week` (`wk`/`sem`); weekday via `LC_TIME=en_US.UTF-8` / `pt_BR.UTF-8` by language; colors from `ckt_color` (`accent`, `magenta`, `cyan`, `orange`, `green`, `yellow`, `red`).
- Subagent line: `subagent.fallback_name` (`agent`/`agente`), `subagent.changes` (`chg.`/`alt.`).
- Dialog: `dialog.close_tab`, `dialog.close_session`, `dialog.still_running`, `dialog.close`, `dialog.cancel`; box colors from palette; confirmation keys stay Enter/y/s and Esc/n/q.
- `close_tab.py`: overlay titles `dialog.close_tab`/`dialog.close_session`; fallback program name `cli.program`.
- `claude-restore`: `cli.already_open`. `ct`: `cli.open_in_kitty_or_tmux`, add `ct --help` text `cli.ct_help` mentioning `ct config` and `ct ./config`.

- [ ] **Step 1: Failing tests** (run each script with `HOME`/`CKT_CONFIG_DIR` temp, strip ANSI):
  - `test_statusline_week_label`: input JSON with `rate_limits.seven_day.used_percentage=15`, `COLUMNS=200` → contains `wk ` for en, `sem ` for pt.
  - `test_subagent_fallback_name`: task without name → `agent` (en) / `agente` (pt).
  - `test_dialog_text`: run `close-tab-dialog.sh tab:1 claude` under `script -qc` with input `\e`, `TERM=xterm`, `COLUMNS=80 LINES=24` → contains `Close this tab?` (en) / `Fechar esta aba?` (pt).
  - `test_statusline_corrupt_settings`: settings file `"{nope"` → still prints the project name, exit 0.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS; `bash -n` all scripts.
- [ ] **Step 5:** Commit per component: `feat(statusline): translate labels and use theme colors`, `feat(kitty): translate close dialog`, `feat(cli): translate ct and helper messages`.

### Task 5: Translate the side panel

**Files:** Modify `claude/session-panel/hooks/register.tsx`, `claude/session-panel/tests/panel.test.tsx`; extend `i18n/*.json` (`panel.*`).

**Interfaces:**
- `async function loadStrings($): Promise<Strings>` in `register.tsx`: reads settings (`$.env.get('CKT_CONFIG_DIR')` or `$HOME/.config/custom-kitty-terminal/settings.json`), resolves repo root via `$.fs.stat($.plugin.root, { resolve: true }).realPath` + `/../..`, reads `i18n/<lang>.json` with `en` fallback per key. Cached; re-read every 5 s via `$.clock.every` (and on `/panel`). Failures → built-in English strings.
- Keys: `panel.title`, `panel.sessions`, `panel.git`, `panel.tasks`, `panel.files`, `panel.reading`, `panel.none_open`, `panel.not_a_repo`, `panel.nothing_changed`, `panel.file`, `panel.files_count`, `panel.others`, `panel.none`, `panel.none_yet`, `panel.more_tasks`, `panel.more_files`, `panel.detached_head`, `panel.kitty_switch_failed`, `panel.command_description`, `panel.opened`. File marks: `panel.mark_read`/`edited`/`created` (`R/E/N` en, `L/E/N` pt).
- Palette: not needed (panel uses Claude theme color names).

- [ ] **Step 1: Failing test:** extend `panel.test.tsx` — mock `fs.stat` (realPath `/repo/claude/session-panel`) and `fs.read` (settings `{"language":"en"}`, `/repo/i18n/en.json` with the real file content read at test time is not possible → inline a minimal en map) and assert `SESSIONS`, `TASKS 0/2`, `R Cargo.toml`; second test with `language: "pt"` asserting `TAREFAS 0/2`, `L Cargo.toml`; third test with `fs.read` rejecting → English labels.
- [ ] **Step 2:** `claude plugin test claude/session-panel` → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Commit: `feat(panel): translate labels via shared i18n`.

### Task 6: Settings menu

**Files:** Create `bin/ct-config`, `lib/menu.py`; Modify `bin/ct` (subcommand `config`), `kitty/kitty.conf` (`map ctrl+shift+f2 launch --type=overlay --title=Settings <repo-agnostic path ~/.local/bin/ct-config>`); extend `i18n/*.json` (`menu.*`); Test `tests/test_menu.py`

**Interfaces:**
- `lib/menu.py`: `class Menu` pure state machine, no curses: `Menu(settings: dict, fonts: list[str])`; `.items() -> list[tuple[str, str]]` (label, current value label); `.key(k: str) -> str | None` with keys `up`, `down`, `enter`, `back`, `quit` → returns `"apply"` when a value changed, `"quit"` on quit, else None; `.view() -> dict` (`{"level": "top"|"sub", "title": str, "rows": list[str], "cursor": int, "message": str}`); `.settings` current dict. Font size sub-list = `range(8, 25)`.
- `bin/ct-config`: curses front-end over `Menu`; on `"apply"` → `save_settings` + `apply()`; shows `menu.applied` (or `menu.applied_claude_new_sessions` per Task 3 finding) or apply messages; colors from `palette()`. Keys: ↑/↓/k/j, Enter, Esc/←/h back, q quit. Language label updates immediately after switching.
- `ct config`: inside kitty → `kitten @ launch --type=overlay --title=<menu.title> ct-config`; else `exec ct-config`.

- [ ] **Step 1: Failing tests** (`tests/test_menu.py`):
  - `test_top_level_lists_four_items`: labels in en = `["Language","Theme","Font","Font size"]`.
  - `test_choose_theme`: down, enter, (down×3), enter → returns `"apply"`, `settings["theme"] == "dracula"`, view back at top.
  - `test_back_from_sub_without_change`: enter, back → `None`, settings unchanged.
  - `test_language_switch_relabels`: choose Português → top labels `["Idioma","Tema","Fonte","Tamanho da fonte"]`.
  - `test_font_size_bounds`: sub-list rows are `"8".."24"`, cursor starts on current size.
  - `test_current_value_marked`: in Theme sub-list, current theme row starts with `●`, others `○`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `Menu`, then `bin/ct-config`, `ct config`, kitty mapping.
- [ ] **Step 4:** PASS; manual: `ct config` inside kitty opens overlay, switching theme repaints kitty, Esc/q closes.
- [ ] **Step 5:** Commit: `feat(menu): add settings menu state machine`, `feat(menu): add curses settings menu and ct config`.

### Task 7: ⚙ button in the tab bar (spike first)

**Files:** Modify `kitty/tab_bar.py`, `kitty/tabs.conf`

**Interfaces:** `tabs.conf`: `tab_bar_style custom`, keep `tab_powerline_style slanted` and new-tab button. `tab_bar.py`: `draw_tab(...)` delegates to `kitty.tab_bar.draw_tab_with_powerline`; when `is_last`, draws ` ⚙ ` right-aligned (record its cell range in a module global). At import: `_install_click_hook()` wraps `kitty.tabs.TabManager.handle_tab_bar_mouse`; single left-click release inside the ⚙ range → `boss.call_remote_control`-free path: `kitty.launch.launch(boss, opts(--type=overlay --title=...), [~/.local/bin/ct-config])`. Whole hook in `try/except`; on failure set `GEAR_ENABLED = False` and skip drawing.

- [ ] **Step 1 (spike):** implement, reload kitty, click ⚙ → menu opens; click tabs, `+`, double-click empty area, middle-click still behave as before. If the hook cannot be made reliable, revert, keep Task 6 shortcut, and note it for the final report.
- [ ] **Step 2:** Visual check: tabs look identical to before (slanted, colors from theme) in fedora and one other theme.
- [ ] **Step 3:** Commit: `feat(kitty): add settings button to tab bar`.

### Task 8: Installer and migration

**Files:** Rewrite `install.sh` (English); Test `tests/test_install.py`

**Behavior:**
- Links: `kitty/{kitty.conf,tabs.conf,tab_bar.py,close_tab.py,close-tab-dialog.sh,save_session.py}` → `~/.config/kitty/`; `bin/{ct,ct-config,claude-panel,claude-restore}` → `~/.local/bin/`; `claude/statusline.sh`, `claude/subagent-statusline.sh` → `~/.claude/`; every `themes/<id>/claude.json` → `~/.claude/themes/<id>.json`; `claude/output-styles/*.md` → `~/.claude/output-styles/`; `claude/session-panel` → `~/.local/share/claude-mods/session-panel`.
- Migration: remove old-name symlinks only if they resolve into the repo (or are dangling and named as the old repo files): `~/.config/kitty/{abas.conf,fechar_aba.py,fechar-aba-dialogo.sh,salvar_sessao.py}`, `~/.local/bin/{claude-painel,claude-restaurar}`, `~/.local/share/claude-mods/painel-sessao`; otherwise warn. Convert `ultima-sessao.kitty-session` → `last-session.kitty-session` (sed `claude-restaurar`→`claude-restore`), remove old file. Same conversion is done by `save_session.py` at save time if the old file reappears.
- Settings file: create if missing; seed `language: "pt"` when `~/.claude/settings.json` has `outputStyle == "Português conciso"`, else `en`.
- `~/.zshrc`: remove the manual block (comment line `# Claude Code com o painel lateral (custom-kitty-terminal)` + the `claude() { … }` function that follows) and write/replace the delimited block `# >>> custom-kitty-terminal >>>` … `# <<< custom-kitty-terminal <<<` with the `claude()` wrapper pointing at `session-panel`.
- Backup `~/.claude/settings.json` as `.bak-<date>` only if apply would change it. Then `bin/ckt-apply`.
- End message tells the user to restart kitty.

- [ ] **Step 1: Failing tests** (run `install.sh` with `HOME=<tmp>`, a fake `PATH` dir containing stub `kitty`, `claude`, `fc-list`, `pkill`):
  - `test_fresh_install_links_and_english_default`: links exist and resolve into repo; settings `language == "en"`; `.zshrc` has exactly one block.
  - `test_migrates_old_layout`: pre-create old symlinks into repo, `ultima-sessao.kitty-session` with a `claude-restaurar abc` line, old manual zshrc function, Claude settings with `outputStyle: "Português conciso"` → old links gone, new session file contains `claude-restore abc`, `language == "pt"`, `.zshrc` has no `painel-sessao` and one block.
  - `test_idempotent`: run twice → no `.bak-*` created on second run, same file tree.
  - `test_foreign_file_not_removed`: a regular file at `~/.config/kitty/abas.conf` is kept.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Commit: `feat(install): install new layout and migrate the Portuguese one`.

### Task 9: README and final pass

- [ ] **Step 1:** Rewrite `README.md` in English (features, install, shortcuts incl. `ctrl+shift+f2` and ⚙, `ct config`, `ct ./config`, files, notes) with a line on switching the UI to Portuguese.
- [ ] **Step 2:** Portuguese sweep: `git grep -nIiE "ção|ões|você|não|aba|sessão|painel" -- . ':!i18n/pt.json' ':!claude/output-styles/portugues-conciso.md' ':!docs'` → no hits except deliberate ones.
- [ ] **Step 3:** All tests: `python3 -m unittest discover -s tests -v` and `claude plugin test claude/session-panel` pass.
- [ ] **Step 4:** Run `./install.sh` on this machine (real migration); `kitty --debug-config` clean; `zsh -ic 'whence -w claude'` → function.
- [ ] **Step 5:** Commit: `docs: rewrite README in English`.
