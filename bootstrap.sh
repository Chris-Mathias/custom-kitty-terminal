#!/usr/bin/env bash
# One command to install (or update) custom-kitty-terminal on Fedora:
#
#   curl -fsSL https://raw.githubusercontent.com/Chris-Mathias/custom-kitty-terminal/main/bootstrap.sh | bash
#
# It installs what is missing (kitty, jq, git, python3, the Adwaita Mono and
# Symbola fonts), offers to install Claude Code, clones this repository into
# ~/.local/share/custom-kitty-terminal (or updates it), runs install.sh and
# offers to make kitty the default terminal. zsh is only installed on request.
#
# Options:
#   --yes                  don't ask; take the defaults (Claude Code: yes,
#                          kitty as default terminal: yes, zsh: no)
#   --zsh                  also install zsh and make it your login shell
#   --no-claude            don't install Claude Code
#   --no-default-terminal  keep your current default terminal
# Environment: CKT_DIR (where to clone), CKT_REPO_URL (what to clone).
set -euo pipefail

REPO_URL=${CKT_REPO_URL:-https://github.com/Chris-Mathias/custom-kitty-terminal.git}
DIR=${CKT_DIR:-$HOME/.local/share/custom-kitty-terminal}

assume=0 want_zsh="" want_claude="" want_terminal=""
for arg in "$@"; do
  case $arg in
    --yes|-y) assume=1 ;;
    --zsh) want_zsh=yes ;;
    --no-claude) want_claude=no ;;
    --no-default-terminal) want_terminal=no ;;
    -h|--help) sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "bootstrap: unknown option $arg (see --help)" >&2; exit 2 ;;
  esac
done

green=$'\e[32m'; yellow=$'\e[33m'; bold=$'\e[1m'; r=$'\e[0m'
step() { printf '\n%s== %s%s\n' "$bold" "$1" "$r"; }
ok()   { printf '%s✓%s %s\n' "$green" "$r" "$1"; }
warn() { printf '%s!%s %s\n' "$yellow" "$r" "$1"; }

# ask "question" default(yes|no) -> 0 for yes. Reads the keyboard even when this
# script comes through `curl | bash`; with --yes or no keyboard, takes the default.
ask() {
  local question=$1 default=$2 hint answer
  [[ $default == yes ]] && hint="[Y/n]" || hint="[y/N]"
  if (( ! assume )) && { exec 3</dev/tty; } 2>/dev/null; then
    printf '%s %s ' "$question" "$hint"
    read -r answer <&3 || answer=""
    exec 3<&-
  else
    answer=""
  fi
  answer=${answer:-$default}
  [[ ${answer,,} == y* ]]
}

# ---------- what to do ----------
if [[ -z $want_claude ]]; then
  if command -v claude >/dev/null; then want_claude=no
  elif ask "Install Claude Code (needed for the side panel and status line)?" yes; then want_claude=yes
  else want_claude=no; fi
fi
if [[ -z $want_terminal ]]; then
  if ask "Make kitty your default terminal (Ctrl+Alt+T, \"Open in terminal\", the dock)?" yes; then
    want_terminal=yes
  else want_terminal=no; fi
fi
if [[ -z $want_zsh ]]; then
  if (( ! assume )) && ask "Install zsh and make it your login shell?" no; then want_zsh=yes; else want_zsh=no; fi
fi

# ---------- packages ----------
step "Packages"
packages=(kitty jq git python3 adwaita-mono-fonts gdouros-symbola-fonts)
[[ $want_zsh == yes ]] && packages+=(zsh)
if command -v dnf >/dev/null; then
  missing=()
  for p in "${packages[@]}"; do rpm -q "$p" >/dev/null 2>&1 || missing+=("$p"); done
  if (( ${#missing[@]} )); then
    sudo dnf install -y "${missing[@]}"
    ok "installed ${missing[*]}"
  else
    ok "everything is already installed"
  fi
else
  warn "this script installs packages with dnf (Fedora). Install these yourself: ${packages[*]}"
fi

# ---------- Claude Code ----------
if [[ $want_claude == yes ]]; then
  step "Claude Code"
  curl -fsSL https://claude.ai/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
  ok "Claude Code installed (run \`claude\` once to sign in)"
fi

# ---------- zsh ----------
if [[ $want_zsh == yes ]]; then
  step "zsh"
  touch "$HOME/.zshrc"
  zsh_path=$(command -v zsh)
  if [[ ${SHELL:-} != "$zsh_path" ]]; then
    chsh -s "$zsh_path"
    export SHELL=$zsh_path
  fi
  ok "zsh is your login shell (from the next login)"
fi

# ---------- this repository ----------
step "custom-kitty-terminal ($DIR)"
if [[ -d $DIR/.git ]]; then
  git -C "$DIR" pull --ff-only
  ok "updated"
else
  mkdir -p "$(dirname "$DIR")"
  git clone "$REPO_URL" "$DIR"
  ok "cloned"
fi
"$DIR/install.sh"

# ---------- default terminal ----------
if [[ $want_terminal == yes ]]; then
  step "kitty as the default terminal"
  python3 -I - "$HOME" <<'PY'
import sys
from pathlib import Path

config = Path(sys.argv[1], ".config")
config.mkdir(parents=True, exist_ok=True)
# xdg-terminal-exec (GNOME's Ctrl+Alt+T and Nautilus' "Open in terminal") takes the first entry.
terms = config / "xdg-terminals.list"
others = [l for l in (terms.read_text().splitlines() if terms.exists() else []) if l.strip() and l.strip() != "kitty.desktop"]
terms.write_text("\n".join(["kitty.desktop", *others]) + "\n")
# x-scheme-handler/terminal in [Default Applications]
apps = config / "mimeapps.list"
lines = apps.read_text().splitlines() if apps.exists() else []
lines = [l for l in lines if not l.startswith("x-scheme-handler/terminal=")]
if "[Default Applications]" not in lines:
    lines = ["[Default Applications]", *([""] if lines else []), *lines] if not lines else lines + ["", "[Default Applications]"]
at = lines.index("[Default Applications]")
lines.insert(at + 1, "x-scheme-handler/terminal=kitty.desktop")
apps.write_text("\n".join(lines) + "\n")
PY
  if command -v gsettings >/dev/null; then
    favorites=$(gsettings get org.gnome.shell favorite-apps 2>/dev/null || echo "")
    if [[ $favorites == \[* ]]; then
      new=$(python3 -I -c '
import ast, sys
apps = ast.literal_eval(sys.argv[1])
swap = {"org.gnome.Ptyxis.desktop", "org.gnome.Terminal.desktop", "org.gnome.Console.desktop"}
out = []
for a in apps:
    a = "kitty.desktop" if a in swap else a
    if a not in out:
        out.append(a)
print(out)' "$favorites")
      [[ $new != "$favorites" ]] && gsettings set org.gnome.shell favorite-apps "$new"
    fi
    # A custom Ctrl+Alt+T shortcut that runs another terminal now runs kitty.
    base=org.gnome.settings-daemon.plugins.media-keys
    for path in $(gsettings get $base custom-keybindings 2>/dev/null | tr -d "[],'@as"); do
      cmd=$(gsettings get "$base.custom-keybinding:$path" command 2>/dev/null || true)
      case $cmd in "'ptyxis'"|"'gnome-terminal'"|"'kgx'") gsettings set "$base.custom-keybinding:$path" command kitty ;; esac
    done
  fi
  ok "kitty opens from Ctrl+Alt+T, \"Open in terminal\" and the dock"
fi

step "Done"
ok "Close and reopen kitty. Settings: ct config (or the ⚙ in the tab bar)."
