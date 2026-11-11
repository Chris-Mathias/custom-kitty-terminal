#!/usr/bin/env bash
# One command to install (or update) custom-kitty-terminal on Linux:
#
#   curl -fsSL https://raw.githubusercontent.com/Chris-Mathias/custom-kitty-terminal/main/bootstrap.sh | bash
#
# It installs what is missing with the system's package manager (dnf, apt,
# pacman or zypper): kitty, jq, git, python3 and the Adwaita Mono and Symbola
# fonts. It offers to install Claude Code, clones this repository into
# ~/.local/share/custom-kitty-terminal (or updates it), runs install.sh and
# offers to make kitty the default terminal. zsh is only installed on request,
# set up like the author's (oh-my-zsh, bira theme, git, autosuggestions and
# syntax highlighting) unless refused.
#
# Options:
#   --yes                  don't ask; take the defaults (Claude Code: yes,
#                          kitty as default terminal: yes, zsh: no)
#   --zsh                  also install zsh and make it your login shell
#   --no-oh-my-zsh         with --zsh: plain zsh, without oh-my-zsh and its plugins
#   --no-claude            don't install Claude Code
#   --no-default-terminal  keep your current default terminal
# Environment: CKT_DIR (where to clone), CKT_REPO_URL (what to clone).
set -euo pipefail

REPO_URL=${CKT_REPO_URL:-https://github.com/Chris-Mathias/custom-kitty-terminal.git}
DIR=${CKT_DIR:-$HOME/.local/share/custom-kitty-terminal}

assume=0 want_zsh="" want_claude="" want_terminal="" want_omz=""
for arg in "$@"; do
  case $arg in
    --yes|-y) assume=1 ;;
    --zsh) want_zsh=yes ;;
    --no-oh-my-zsh) want_omz=no ;;
    --no-claude) want_claude=no ;;
    --no-default-terminal) want_terminal=no ;;
    -h|--help) sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
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
if [[ $want_zsh == yes && -z $want_omz ]]; then
  if ask "Set zsh up with oh-my-zsh (bira theme, git, autosuggestions, syntax highlighting)?" yes; then
    want_omz=yes
  else want_omz=no; fi
fi

# ---------- packages ----------
step "Packages"
# Package names differ between distributions; the fonts may not exist at all
# (Symbola is only in the AUR on Arch), so they are tried one by one.
if command -v dnf >/dev/null; then
  pm=dnf; base=(kitty jq git python3); fonts=(adwaita-mono-fonts gdouros-symbola-fonts)
  have() { rpm -q "$1" >/dev/null 2>&1; }
  install() { sudo dnf install -y "$@"; }
elif command -v apt-get >/dev/null; then
  pm=apt; base=(kitty jq git python3); fonts=(fonts-adwaita-mono fonts-symbola)
  have() { dpkg -s "$1" >/dev/null 2>&1; }
  install() { sudo apt-get install -y "$@"; }
elif command -v pacman >/dev/null; then
  pm=pacman; base=(kitty jq git python); fonts=(adwaita-fonts)
  have() { pacman -Q "$1" >/dev/null 2>&1; }
  install() { sudo pacman -S --needed --noconfirm "$@"; }
elif command -v zypper >/dev/null; then
  pm=zypper; base=(kitty jq git python3); fonts=(adwaita-fonts gdouros-symbola-fonts)
  have() { rpm -q "$1" >/dev/null 2>&1; }
  install() { sudo zypper --non-interactive install "$@"; }
else
  pm=""
fi
[[ $want_zsh == yes ]] && base+=(zsh)
if [[ -n $pm ]]; then
  missing=()
  for p in "${base[@]}"; do have "$p" || missing+=("$p"); done
  [[ $pm == apt && ${#missing[@]} -gt 0 ]] && sudo apt-get update
  if (( ${#missing[@]} )); then
    install "${missing[@]}"
    ok "installed ${missing[*]}"
  else
    ok "kitty, jq, git and python are already installed"
  fi
  for f in "${fonts[@]}"; do
    have "$f" || install "$f" >/dev/null 2>&1 || warn "couldn't install the font package $f; pick a font in ct config"
  done
else
  warn "no dnf, apt, pacman or zypper here: install these yourself: kitty jq git python3 (and zsh with --zsh)"
fi
for cmd in kitty git python3; do
  command -v "$cmd" >/dev/null || { warn "$cmd is missing; install it and run this again"; exit 1; }
done

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
  if [[ $want_omz == yes ]]; then
    # oh-my-zsh and the two plugins straight from git: oh-my-zsh's own installer
    # would change the shell and replace ~/.zshrc by itself.
    omz="$HOME/.oh-my-zsh"
    [[ -d $omz ]] || git clone --depth 1 https://github.com/ohmyzsh/ohmyzsh.git "$omz"
    for plugin in zsh-autosuggestions zsh-syntax-highlighting; do
      dest="${ZSH_CUSTOM:-$omz/custom}/plugins/$plugin"
      [[ -d $dest ]] || git clone --depth 1 "https://github.com/zsh-users/$plugin.git" "$dest"
    done
    python3 -I - "$HOME/.zshrc" "$omz/templates/zshrc.zsh-template" <<'PY'
import re, sys
from pathlib import Path

zshrc, template = Path(sys.argv[1]), Path(sys.argv[2])
wanted = ["git", "zsh-autosuggestions", "zsh-syntax-highlighting"]
text = zshrc.read_text()
if not text.strip() and template.exists():
    # New ~/.zshrc: oh-my-zsh's template with the bira theme and the plugins.
    text = template.read_text()
    text = re.sub(r'^ZSH_THEME=.*$', 'ZSH_THEME="bira"', text, flags=re.M)
    text = re.sub(r'^plugins=\(.*?\)', f"plugins=({' '.join(wanted)})", text, flags=re.M | re.S)
elif re.search(r'^\s*source .*oh-my-zsh\.sh', text, flags=re.M):
    # Already on oh-my-zsh: only the missing plugins (syntax highlighting goes last).
    def add(m):
        have = m.group(1).split()
        keep = [p for p in have if p != "zsh-syntax-highlighting"]
        keep += [p for p in wanted if p not in have and p != "zsh-syntax-highlighting"]
        return f"plugins=({' '.join(keep + ['zsh-syntax-highlighting'])})"
    if re.search(r'^plugins=\(', text, flags=re.M):
        text = re.sub(r'^plugins=\((.*?)\)', add, text, count=1, flags=re.M | re.S)
else:
    # A ~/.zshrc without oh-my-zsh: load it in a block of its own.
    text = text.rstrip("\n") + ("\n\n" if text.strip() else "") + (
        "# >>> custom-kitty-terminal oh-my-zsh >>>\n"
        'export ZSH="$HOME/.oh-my-zsh"\n'
        'ZSH_THEME="bira"\n'
        f"plugins=({' '.join(wanted)})\n"
        "source $ZSH/oh-my-zsh.sh\n"
        "# <<< custom-kitty-terminal oh-my-zsh <<<\n")
zshrc.write_text(text)
PY
    ok "oh-my-zsh with the bira theme, git, autosuggestions and syntax highlighting"
  fi
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
    # Ctrl+Alt+T, system-wide: GNOME grabs the key before kitty sees it, so it runs
    # ckt-claude-tab (new Claude tab in kitty, or starts kitty). A custom shortcut
    # already on Ctrl+Alt+T, or one that opens another terminal, is repointed;
    # otherwise one is added.
    base=org.gnome.settings-daemon.plugins.media-keys
    runner="$HOME/.local/bin/ckt-claude-tab"
    found=""
    # The list prints as ['/path/a/', '/path/b/'] (or @as [] when empty): keep the quoted paths.
    for path in $(gsettings get $base custom-keybindings 2>/dev/null | grep -o "'[^']*'" | tr -d "'"); do
      key="$base.custom-keybinding:$path"
      cmd=$(gsettings get "$key" command 2>/dev/null || true)
      binding=$(gsettings get "$key" binding 2>/dev/null || true)
      case "$binding|$cmd" in
        "'<Control><Alt>t'|"*|"'<Primary><Alt>t'|"*|*"|'ptyxis'"|*"|'gnome-terminal'"|*"|'kgx'"|*"|'kitty'")
          gsettings set "$key" command "$runner"
          found=1 ;;
      esac
    done
    if [[ -z $found ]]; then
      path=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom-kitty-terminal/
      list=$(gsettings get $base custom-keybindings 2>/dev/null || echo "@as []")
      new=$(python3 -I -c '
import ast, sys
raw = sys.argv[1].removeprefix("@as ").strip()
paths = ast.literal_eval(raw) if raw else []
if sys.argv[2] not in paths:
    paths.append(sys.argv[2])
print(paths)' "$list" "$path")
      gsettings set $base custom-keybindings "$new"
      gsettings set "$base.custom-keybinding:$path" name "Claude (kitty)"
      gsettings set "$base.custom-keybinding:$path" command "$runner"
      gsettings set "$base.custom-keybinding:$path" binding "<Control><Alt>t"
    fi
  fi
  ok "kitty opens from Ctrl+Alt+T, \"Open in terminal\" and the dock"
fi

step "Done"
ok "Close and reopen kitty. Settings: ct config (or the ⚙ in the tab bar)."
