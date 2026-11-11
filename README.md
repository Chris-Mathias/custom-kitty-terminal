# custom-kitty-terminal

A [kitty](https://sw.kovidgoyal.net/kitty/) and [Claude Code](https://code.claude.com) setup for working with many sessions and many repositories at once, on Linux. Made on Fedora with GNOME; the installer also handles Debian, Ubuntu, Linux Mint, Arch and openSUSE, and the GNOME, KDE Plasma and Cinnamon desktops.

- **Looks like GNOME's terminal out of the box**: GNOME palette, Adwaita Mono font (the system's monospace font when it isn't available), the desktop's own title bar.
- **Settings menu** (`ct config`, `Ctrl+Shift+F2` or the ⚙ at the right of the tab bar): language (English or Português), look, Claude Code, behavior and every shortcut — see [Settings](#settings).
- **Seven themes**, each changing kitty and Claude Code together: Fedora, Catppuccin (Mocha), Tokyo Night, Dracula, Gruvbox (dark), Light and Noctalia.
- **Slanted tabs** on top, with the title Claude gives each session and a `+` button.
- **Reopens as you left it**: when kitty starts, last time's tabs come back and each Claude resumes the same conversation.
- **Several Claude sessions in the same tab**, stacked, switched from the side panel.
- **Close with confirmation** only when something is running, in its own dialog.
- **Claude Code**: one-line status line (project, worktree, model, context and 5h/weekly limits), subagent lines with each one's branch/worktree, themed colors and spinner verbs in your language. Claude's response style is left as you set it.
- **Side panel** (`session-panel` mod): open sessions, running subagents, tasks, git (with worktrees) and files touched. Click a subagent (or press its number with the panel focused, or type `/agent 2`, `/agent next`, `/agent prev`, `/agent main`) to see its conversation; `0` or `/agent main` goes back.

## Install

One command, which also updates an existing install:

```sh
curl -fsSL https://raw.githubusercontent.com/Chris-Mathias/custom-kitty-terminal/main/bootstrap.sh | bash
```

It installs what is missing with your package manager (dnf, apt, pacman or zypper): kitty, jq, git, python3 and the Adwaita Mono and Symbola fonts. kitty must be 0.46 or newer; when the distribution's is older (Debian, Ubuntu and Mint) or missing, the official kitty build is installed in `~/.local/kitty.app` instead. It asks whether to install Claude Code and whether to make kitty your default terminal, clones the repository into `~/.local/share/custom-kitty-terminal` (`CKT_DIR` changes it) and runs `install.sh`. zsh is installed only with `--zsh` (or when you say yes to it), set up like the author's: oh-my-zsh with the `bira` theme and the `git`, `zsh-autosuggestions` and `zsh-syntax-highlighting` plugins. An existing `~/.zshrc` is never replaced, only completed; `--no-oh-my-zsh` gives a plain zsh. `--yes` takes the defaults without asking. Font packages that a distribution doesn't have are skipped with a note. Without Claude Code everything kitty-side still works; the side panel, the status line and the Claude shortcuts need it.

### By hand

Dependencies:

```sh
# kitty 0.46 or newer, jq, git and python3, e.g.
sudo dnf install kitty jq git python3          # Fedora
sudo apt install jq git python3                # Debian / Ubuntu / Mint, plus the official kitty:
curl -L https://sw.kovidgoyal.net/kitty/installer.sh | sh /dev/stdin
# Claude Code 2.1.287 or newer (the side panel needs it)
```

Then:

```sh
git clone https://github.com/Chris-Mathias/custom-kitty-terminal.git
cd custom-kitty-terminal
./install.sh
```

`install.sh` links each file of this repository into place (symbolic links), keeps whatever was there with a `.bak-<date>` suffix, merges only the keys this project owns into `~/.claude/settings.json` (theme, spinner verbs, status lines; a response style only if you turn it on) and adds a small `claude()` function to `~/.zshrc` and/or `~/.bashrc` so that `claude` opens with the side panel. It starts in English; switch to Portuguese with `ct config`. To update later: `git pull`, then `./install.sh` again (it regenerates the files the settings menu writes).

Close and reopen kitty. The first time it opens an empty tab; from then on it saves and reopens the tabs by itself.

Upgrading from the older Portuguese version of this repo: just run `./install.sh` again. It removes the old links, converts the saved tabs and keeps Portuguese as your language.

## Settings

`ct config` (or `Ctrl+Shift+F2`, or the ⚙ in the tab bar) opens the menu. It starts with the groups below and the language; `↑`/`↓` and `Enter` go in, `Esc` goes back and `q` closes. Every change is applied right away: kitty reloads, and Claude Code picks up the rest (sessions that are already open may need a restart).

| Group | Settings |
|---|---|
| Appearance | theme, font, font size, line height, padding, tab style (slanted, round, angled, separators), tab bar on top or bottom, transparency, cursor shape and blink, title bar (the system's, kitty's own, none — needs a kitty restart), ligatures |
| Claude Code | response style (off by default; when on: response language and length — short, balanced, detailed), status line items, the subagent list below the prompt (shown or hidden — the subagents are also in the side panel), side panel sections (sessions, subagents, tasks, git, files), their order and whether it opens by itself, phrases while thinking (ours or Claude's) |
| Behavior | reopen tabs on start, confirm before closing (only if something runs, always, never), whether kitty keeps `Ctrl+W`/`Ctrl+N`, scrollback lines, bell, a close button (×) on each tab, a close button (×) on each session in the side panel (both off by default; they ask before closing like `Ctrl+W`) |
| Shortcuts | every shortcut in the table below: pick one, choose "Record new keys" and press the combination. If it's already used (by this project or by kitty), the menu asks before swapping. "Reset to default" and "Reset all" undo changes. |

The response style is never touched unless you turn it on. When you do, the menu writes one style file (`~/.claude/output-styles/custom-kitty-terminal.md`) and remembers the style you had before; turning it off puts that one back.

Your choices are saved in `~/.config/custom-kitty-terminal/settings.json`, outside the repository.

## kitty shortcuts

The defaults (change any of them in Settings → Shortcuts):

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
bootstrap.sh  one-command install/update (packages, Claude Code, zsh, default terminal)
install.sh    links everything into place and applies your settings
kitty/      kitty.conf, tabs.conf (tab style), tab_bar.py (tabs + ⚙ button),
            close_tab.py + close-tab-dialog.sh (Ctrl+W), save_session.py (reopen tabs)
bin/        ct, ct-config (settings menu), ckt-apply, claude-panel, claude-restore
lib/        ckt.py / ckt.sh (settings, translations, themes), menu.py, shortcuts.py
i18n/       en.json, pt.json: every text shown to you
themes/     <theme>/kitty.conf, claude.json, palette.json
claude/     statusline.sh, subagent-statusline.sh,
            session-panel/ (the side panel mod)
tests/      python3 -m unittest discover -s tests; claude plugin test claude/session-panel
```

The list of saved tabs (`~/.config/kitty/last-session.kitty-session`) and the files the settings menu writes (`~/.config/kitty/generated/`: theme, font, appearance, behavior, shortcuts) belong to each computer and stay out of the repository.

## Notes

- On GNOME, the system's title bar makes kitty run through XWayland (`linux_display_server x11`): GNOME only draws its own title bar for X11 windows. Other desktops draw it for Wayland windows too, so kitty runs natively there. Pick "kitty's own" in Settings → Appearance → Title bar to avoid XWayland on GNOME.
- **Default terminal and Ctrl+Alt+T** (when you say yes in the installer): on GNOME, Ctrl+Alt+T opens a Claude tab in kitty (`ckt-claude-tab`) and kitty replaces the terminal in the dock; on KDE Plasma, kitty becomes the default terminal and Ctrl+Alt+T moves from Konsole to `ckt-claude-tab` (after logging out and back in); on Cinnamon (Mint), kitty becomes the terminal Ctrl+Alt+T opens. On other desktops, set it in their settings; `xdg-terminal-exec` users get kitty first everywhere.
- The ⚙ button relies on a small hook into kitty's tab bar code. If a kitty update breaks that hook, the button simply disappears and the tabs keep working; `ct config` and `Ctrl+Shift+F2` still open the menu.
- The Claude shortcuts call your `$SHELL` in interactive mode, to load your `~/.zshrc`.
- The side panel runs inside Claude Code with your user's permissions; it reads `git`, `claude agents --json`, `~/.claude/sessions` and the settings file, and talks to kitty over the control socket (`allow_remote_control socket-only`).
