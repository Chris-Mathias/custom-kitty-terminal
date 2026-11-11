# More Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grouped settings menu with appearance, Claude Code, behavior and shortcut settings, including an opt-in Claude response style and press-to-record shortcuts.

**Architecture:** `lib/ckt.py` grows the settings model and writes three more generated kitty files (`appearance.conf`, `behavior.conf`, `shortcuts.conf`); `kitty.conf` keeps only fixed lines and includes them. A shortcut table lives in `lib/shortcuts.py`. The menu becomes a tree (`lib/menu.py`) drawn by `bin/ct-config`, with a capture screen that reads keys through kitty's keyboard protocol while a kitty keyboard mode suspends kitty's own shortcuts.

**Tech Stack:** python3 stdlib (json, curses, termios), bash + jq, kitty 0.47 config/remote control, Claude Code mod API (TSX).

**Spec:** `docs/superpowers/specs/2026-11-11-more-settings-design.md`

## Global Constraints

- Defaults reproduce today's behavior exactly; an old 4-key settings file loads with defaults for everything new.
- Response style OFF by default; project never writes `outputStyle`/style file unless enabled; restores the user's previous `outputStyle` when disabled.
- `spinnerVerbs`: written only when `spinner == "ours"`; with `"claude"` removed only if it equals one of our lists.
- Every option value must keep kitty's config valid (`load_config` bad lines = 0).
- All user-facing text through `i18n/{en,pt}.json` (same key sets).
- Commits: small, Conventional Commits, short, no co-author trailer. Branch: `feat/english-and-settings-menu` (continue).
- Tests: `python3 -m unittest discover -s tests` and `claude plugin test claude/session-panel`.

## Settings model (Task 1 produces; all later tasks consume)

| key | values | default |
|---|---|---|
| `line_height` | 100,105,…,130 | 115 |
| `padding` | `compact` (`2 4`), `normal` (`4 8`), `roomy` (`8 16`) | `normal` |
| `tab_style` | `slanted`, `round`, `angled`, `separators` | `slanted` |
| `tab_position` | `top`, `bottom` | `top` |
| `opacity` | 70,75,…,100 | 100 |
| `cursor_shape` | `block`, `beam`, `underline` | `block` |
| `cursor_blink` | bool | true |
| `title_bar` | `gnome`, `kitty`, `none` | `gnome` |
| `ligatures` | bool | true |
| `response_style` | `{"enabled": bool, "language": "pt"\|"en", "length": "short"\|"balanced"\|"detailed", "previous": str\|null}` | `{"enabled": false, "language": "pt", "length": "short", "previous": null}` |
| `spinner` | `ours`, `claude` | `ours` |
| `status_line` | `{"context","five_hour","weekly","resets","model","worktree": bool}` | all true |
| `panel` | `{"sections": permutation-subset of ["sessions","git","tasks","files"], "auto_open": bool}` | all four in that order, true |
| `reopen_tabs` | bool | true |
| `confirm_close` | `running`, `always`, `never` | `running` |
| `kitty_ctrl_keys` | bool | true |
| `scrollback` | 5000, 10000, 20000, 50000, 100000 | 20000 |
| `bell` | bool | false |
| `shortcuts` | `{action_id: "ctrl+alt+t"}` overrides only | `{}` |

Nested dicts validate per field (bad field → default field).

## Review Focus

- Menu closed or crashing during key capture: kitty's shortcuts must come back (test: capture helper always pops the mode in `finally`).
- Two actions on the same keys after a swap/reset: generated `shortcuts.conf` must never contain duplicate keys (test in Task 3).
- `panel.sections` empty or with unknown names: panel shows defaults / skips unknown (test in Task 5).
- Disabling the response style after the user changed `outputStyle` by hand to something else: leave it alone (test in Task 4).
- `title_bar: kitty`/`none` while `linux_display_server x11` is fixed in kitty.conf: generated value must override (include order) (test in Task 2).

---

### Task 1: Settings model

**Files:** Modify `lib/ckt.py`; Test `tests/test_settings_model.py`
**Produces:** `DEFAULTS` extended per the table; `CHOICES: dict[str, tuple]` for every scalar key; `load_settings()` validates nested dicts per field; `PANEL_SECTIONS = ("sessions","git","tasks","files")`; `STATUS_ITEMS = ("context","five_hour","weekly","resets","model","worktree")`.

- [ ] Tests: `test_old_file_gets_new_defaults` (4-key file → every new key default); `test_bad_nested_field_falls_back` (`status_line: {"model": "x"}` → model True, others True); `test_panel_sections_validated` (`["git","nope","git"]` → `["git"]`; `[]` allowed → `[]`); `test_bool_keys_reject_strings`; `test_shortcut_overrides_kept_only_for_known_ids` (Task 3 table; skip until then — write after Task 3 instead, in Task 3).
- [ ] Run → FAIL. Implement. Run → PASS. Commit `feat(settings): add the new settings and their defaults`.

### Task 2: kitty appearance and behavior

**Files:** Modify `lib/ckt.py` (`write_kitty_includes`), `kitty/kitty.conf`, `kitty/tabs.conf`, `kitty/tab_bar.py`, `kitty/close_tab.py`; Test `tests/test_kitty_generated.py`
**Produces:** `appearance_conf(s) -> str`, `behavior_conf(s) -> str` (pure); `write_kitty_includes` also writes `appearance.conf`, `behavior.conf`.

- `appearance.conf`: `modify_font cell_height {line_height}%`, `window_padding_width {…}`, `tab_powerline_style {slanted|round|angled}` (separators → `slanted`, tab_bar.py draws separators), `tab_bar_edge {top|bottom}`, `background_opacity {opacity/100}`, `cursor_shape`, `cursor_blink_interval {-1|0}`, title bar (`gnome`: `linux_display_server x11` + `hide_window_decorations no`; `kitty`: `linux_display_server auto` + `hide_window_decorations no`; `none`: `hide_window_decorations yes`), `disable_ligatures {never|always}`.
- `behavior.conf`: reopen → `startup_session last-session.kitty-session` + `watcher save_session.py`, else `startup_session none`; `scrollback_lines`; bell → `enable_audio_bell yes|no`.
- `kitty.conf`: drop those lines; add `dynamic_background_opacity yes`; includes after fixed lines: theme, font, appearance, behavior, shortcuts (Task 3).
- `tab_bar.py`: reads `ckt.load_settings()["tab_style"]` at import; `separators` → `draw_tab_with_separator`, else powerline; ⚙ logic unchanged.
- `close_tab.py`: `confirm_close` (`always` asks even when idle, listing "nothing running" via i18n `dialog.nothing_running`; `never` closes at once).

- [ ] Tests: `test_defaults_match_today` (default appearance+behavior text contains `modify_font cell_height 115%`, `window_padding_width 4 8`, `tab_powerline_style slanted`, `tab_bar_edge top`, `background_opacity 1.0`, `linux_display_server x11`, `startup_session last-session.kitty-session`, `watcher save_session.py`, `scrollback_lines 20000`, `enable_audio_bell no`, `disable_ligatures never`); one test per option value (`test_title_bar_none`, `test_reopen_off`, `test_opacity_85` → `0.85`, …); `test_every_value_is_valid_kitty_config` (kitty +runpy load_config over the cross product sampled per key → 0 bad lines; skip without kitty); `test_title_bar_override_order` (generated includes come after any fixed `linux_display_server`; kitty.conf contains none).
- [ ] Run → FAIL. Implement. PASS. Commit `feat(kitty): generate appearance and behavior settings`.
- [ ] Verify live: `ckt-apply`, kitty reload, opacity change applies (record), ⚙ shows with each tab style.

### Task 3: Shortcuts

**Files:** Create `lib/shortcuts.py`; Modify `lib/ckt.py`, `kitty/kitty.conf` (remove all `map`), i18n; Test `tests/test_shortcuts.py`
**Produces:**
- `ACTIONS: tuple[Action, ...]`, `Action(id, default, kitty_action, label_key)`; ids: `claude_tab ctrl+alt+t`, `claude_stack ctrl+alt+n`, `prev_session alt+up`, `next_session alt+down`, `toggle_stack ctrl+alt+z`, `close_session ctrl+alt+w`, `close_tab ctrl+w`, `new_tab ctrl+n`, `new_tab_2 alt+t`, `new_tab_3 ctrl+shift+t`, `tab_1..tab_6 alt+1..6`, `prev_tab alt+left`, `next_tab alt+right`, `split_right ctrl+shift+enter`, `split_below ctrl+shift+minus`, `settings ctrl+shift+f2` (kitty actions copied from today's kitty.conf).
- `keys_for(s) -> dict[id, str]`; `shortcuts_conf(s) -> str` (one `map`, skips `ctrl+w`/`ctrl+n` when `kitty_ctrl_keys` false, never two maps on one key — later override wins, earlier action dropped); `assign(s, id, keys) -> tuple[dict, str|None]` (returns new settings and id of the action that had those keys, which gets the old keys of `id` = swap); `reset(s, id)`, `reset_all(s)`.
- `normalize(keys) -> str` (lowercase, modifier order `ctrl+alt+shift+super`); `from_csi_u(seq: bytes) -> str|None` (kitty keyboard protocol `CSI key;mods u` and `CSI 1;mods {A,B,C,D,…}` / `~` forms → notation; Enter=`enter`, `-`=`minus`).
- `kitty_default_action(keys) -> str|None` via `kitty +runpy` (cached) listing kitty's default keymap.
- shortcuts.conf also defines the capture mode: `map --new-mode ckt-capture --on-unknown passthrough kitty_mod+f2 pop_keyboard_mode`… builder adjusts after spike.

- [ ] Spike (throwaway): confirm `kitten @ action push_keyboard_mode ckt-capture` from an overlay passes a mapped combo (`ctrl+w`) to the program and `pop_keyboard_mode` restores. Record result.
- [ ] Tests: `test_default_conf_matches_today` (set of `map` lines equals today's 23 maps); `test_override_and_swap`; `test_no_duplicate_keys`; `test_ctrl_keys_off_drops_ctrl_w_and_ctrl_n`; `test_normalize`; `test_from_csi_u` (`b"\x1b[116;7u"` → `ctrl+alt+t`; `b"\x1b[1;3A"` → `alt+up`; `b"\x1b[13;6u"` → `ctrl+shift+enter`); `test_unknown_override_ids_dropped`.
- [ ] FAIL → implement → PASS. Commit `feat(shortcuts): generate kitty shortcuts from settings`.

### Task 4: Claude side (response style, spinner)

**Files:** Modify `lib/ckt.py` (`claude_values`/`merge_claude_settings`), i18n (`style.*` texts per language × length); Test `tests/test_claude_settings.py`
**Produces:** `style_name(rs) -> str` (`"Terminal — Português, curto"` / `"Terminal — English, short"` etc. from i18n), `style_file(rs) -> str`; merge rules per Global Constraints; style file `~/.claude/output-styles/custom-kitty-terminal.md`.

- [ ] Tests: `test_style_off_writes_nothing`; `test_enable_saves_previous_and_sets_name`; `test_disable_restores_previous`; `test_disable_removes_key_when_no_previous`; `test_disable_leaves_hand_changed_style`; `test_style_file_written_and_removed`; `test_spinner_claude_removes_only_ours`; `test_spinner_claude_keeps_user_list`.
- [ ] FAIL → implement → PASS. Commit `feat(claude): opt-in response style and spinner choice`.

### Task 5: Status line items and panel options

**Files:** Modify `claude/statusline.sh`, `claude/session-panel/hooks/register.tsx`, panel test; Test `tests/test_shell_i18n.py`
- statusline: hide segments by `status_line.*` (jq read once).
- panel: read `panel.sections` (order) and `auto_open` with the strings refresh; unknown names skipped; empty list → nothing but the title.
- [ ] Tests: `test_statusline_hides_items` (weekly off → no `wk`; model off → no model); panel tests `the panel follows section order and visibility` (sections `["files","git"]` → FILES before GIT, no SESSIONS) and `the panel stays closed when auto_open is off` (no `ui.open` during session.start).
- [ ] FAIL → implement → PASS. Commits `feat(statusline): hide items from settings`, `feat(panel): choose sections, order and auto open`.

### Task 6: Menu tree

**Files:** Rewrite `lib/menu.py`; Test `tests/test_menu.py` (rewrite)
**Produces:** `Menu(settings, fonts)` with levels: top (groups + language) → group (items) → item (choices | order editor | capture). `key(k)` handles `up/down/enter/back/quit` and returns `"apply"`, `"quit"`, `"capture"` (front end must read a key combo) or None; `captured(keys) -> str|None` (applies `shortcuts.assign`, returns `"apply"` or `"confirm"` when the combo belongs to a kitty default action or another project action, exposing `pending`; `key("enter")` confirms, `back` cancels). Toggle items show On/Off. Status line item opens a list of toggles. Panel sections: list with `space`-less flow: Enter picks a row up ("moving"), up/down moves it, Enter drops; a separate row per section toggles visibility. Shortcuts group: rows per action + "Reset all"; item level: "Record new keys", "Reset to default".
- [ ] Tests (replace old ones): top level = `[Appearance, Claude Code, Behavior, Shortcuts, Language]`; navigate to theme and choose (apply); toggle ligatures; response style enable flow; status line toggle; panel move `files` to first; shortcut capture flow (`capture` → `captured("ctrl+alt+y")` → apply, settings changed); conflict flow (`captured("ctrl+w")` → `confirm` → enter → swap); `ctrl_keys` off refuses `ctrl+w`; language switch relabels.
- [ ] FAIL → implement → PASS. Commit `feat(menu): group settings and add shortcut capture`.

### Task 7: Menu front end

**Files:** Modify `bin/ct-config`; i18n `menu.*`
- Draw any level from `view()`; capture screen: push kitty keyboard mode (`kitten @ action push_keyboard_mode ckt-capture`), enable keyboard protocol (`\x1b[>1u`), read raw bytes with `os.read` in cbreak until a CSI u/arrow sequence with a non-modifier key, `from_csi_u`, pass to `captured`; always pop mode and protocol (`\x1b[<u`) in `finally`; Esc alone cancels.
- Messages for "after restart" items (title bar), conflicts and refusals.
- [ ] Smoke test in pty (extend `tests/` with a pty test that navigates Appearance → Ligatures → Off and checks settings) → PASS. Manual capture check in kitty. Commit `feat(menu): draw groups and record shortcuts`.

### Task 8: Install, README, final pass

- [ ] `install.sh` unchanged flow (apply writes the new files); test `test_fresh_install_links_and_english_default` asserts the three new generated files exist and kitty.conf has no `map` lines.
- [ ] README: settings list per group, shortcut customization, upgrade note (`git pull` + `./install.sh`).
- [ ] Full suites green; `./install.sh` on this machine; kitty load_config 0 bad lines.
- [ ] Commit `docs: describe the new settings`.
