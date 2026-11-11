# custom-kitty-terminal

A [kitty](https://sw.kovidgoyal.net/kitty/) and [Claude Code](https://code.claude.com) setup for working with many sessions and many repositories at once, on Fedora (GNOME).

- **Looks like Ptyxis out of the box**: GNOME palette, Adwaita Mono font, GNOME title bar.
- **Settings menu** (`ct config`, `Ctrl+Shift+F2` or the ⚙ at the right of the tab bar): language (English or Português), theme, font and font size.
- **Six themes**, each changing kitty and Claude Code together: Fedora, Catppuccin (Mocha), Tokyo Night, Dracula, Gruvbox (dark) and Light.
- **Slanted tabs** on top, with the title Claude gives each session and a `+` button.
- **Reopens as you left it**: when kitty starts, last time's tabs come back and each Claude resumes the same conversation.
- **Several Claude sessions in the same tab**, stacked, switched from the side panel.
- **Close with confirmation** only when something is running, in its own dialog.
- **Claude Code**: one-line status line (project, worktree, model, context and 5h/weekly limits), subagent lines with each one's branch/worktree, themed colors and spinner verbs in your language. Claude's response style is left as you set it.
- **Side panel** (`session-panel` mod): open sessions, git (with worktrees), tasks and files touched.

## Install

Dependencies:

```sh
sudo dnf install kitty jq git python3
# Claude Code 2.1.287 or newer (the side panel needs it)
```

Then:

```sh
git clone https://github.com/Chris-Mathias/custom-kitty-terminal.git
cd custom-kitty-terminal
./install.sh
```

`install.sh` links each file of this repository into place (symbolic links), keeps whatever was there with a `.bak-<date>` suffix, merges only the keys this project owns into `~/.claude/settings.json` (theme, spinner verbs, status lines; never your response style) and adds a small `claude()` function to `~/.zshrc` so that `claude` opens with the side panel. It starts in English; switch to Portuguese with `ct config`. To update later: `git pull`.

Close and reopen kitty. The first time it opens an empty tab; from then on it saves and reopens the tabs by itself.

Upgrading from the older Portuguese version of this repo: just run `./install.sh` again. It removes the old links, converts the saved tabs and keeps Portuguese as your language.

## Settings

`ct config` (or `Ctrl+Shift+F2`, or the ⚙ in the tab bar) opens the menu. Pick a row with `↑`/`↓` and `Enter`, then a value; `Esc` goes back and `q` closes. Every change is applied right away: kitty reloads, and Claude Code gets the new theme and spinner verbs (sessions that are already open may need a restart).

Your choices are saved in `~/.config/custom-kitty-terminal/settings.json`, outside the repository.

## kitty shortcuts

| Shortcut | What it does |
|---|---|
| `Ctrl+Alt+T` | New Claude session in a new tab |
| `Ctrl+Alt+N` | New Claude session in the same tab (stacked) |
| `Alt+↑` / `Alt+↓` | Previous / next session within the tab |
| `Ctrl+Alt+Z` | Toggles between stack (one at a time) and split screen |
| `Ctrl+Alt+W` | Closes the front session (asks if something is running) |
| `Ctrl+W` | Closes the tab (asks if something is running) |
| `Ctrl+N`, `Alt+T`, `+` button | New tab with just the shell |
| `Alt+1…6`, `Alt+←/→` | Switch tabs |
| `Ctrl+Shift+Enter` / `Ctrl+Shift+-` | Split the screen side by side / top and bottom |
| `Ctrl+Shift+H` | Whole scrollback with search |
| `Ctrl+Shift+F2` | Settings menu |
| `Ctrl+Shift+F5` | Reload the configuration |

`Ctrl+W` and `Ctrl+N` belong to kitty: to delete the previous word in the shell or in Claude, use `Alt+Backspace`.

## Commands

- `ct [folder]`: opens Claude (with the panel) in a new tab.
- `ct -a [folder]`: opens it in the same tab, stacked.
- `ct [folder] -- -w name`: passes arguments to `claude` (here, a new worktree called "name").
- `ct config`: settings menu. For a folder literally named `config`, use `ct ./config`.
- `claude-panel`: runs Claude with the panel in the current tab.

## Files

```
kitty/      kitty.conf, tabs.conf (tab style), tab_bar.py (tabs + ⚙ button),
            close_tab.py + close-tab-dialog.sh (Ctrl+W), save_session.py (reopen tabs)
bin/        ct, ct-config (settings menu), ckt-apply, claude-panel, claude-restore
lib/        ckt.py / ckt.sh (settings, translations, themes), menu.py
i18n/       en.json, pt.json: every text shown to you
themes/     <theme>/kitty.conf, claude.json, palette.json
claude/     statusline.sh, subagent-statusline.sh,
            session-panel/ (the side panel mod)
tests/      python3 -m unittest discover -s tests; claude plugin test claude/session-panel
```

The list of saved tabs (`~/.config/kitty/last-session.kitty-session`) and the generated theme/font files (`~/.config/kitty/generated/`) belong to each computer and stay out of the repository.

## Notes

- kitty runs through XWayland (`linux_display_server x11`) so GNOME draws the title bar with the standard buttons. For kitty's own title bar, delete that line.
- The ⚙ button relies on a small hook into kitty's tab bar code. If a kitty update breaks that hook, the button simply disappears and the tabs keep working; `ct config` and `Ctrl+Shift+F2` still open the menu.
- The Claude shortcuts call your `$SHELL` in interactive mode, to load your `~/.zshrc`.
- The side panel runs inside Claude Code with your user's permissions; it reads `git`, `claude agents --json`, `~/.claude/sessions` and the settings file, and talks to kitty over the control socket (`allow_remote_control socket-only`).
