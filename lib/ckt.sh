# Shell side of lib/ckt.py: reads the user's settings, translations and theme
# palette. Source it from bash; needs jq. Every lookup falls back to defaults.
#   ckt_lang          -> en | pt
#   ckt_theme         -> fedora | catppuccin | ...
#   ckt_t <key>       -> translated text (English, then the key itself, as fallbacks)
#   ckt_color <name>  -> ANSI foreground escape for a palette color
#   ckt_bg <name>     -> ANSI background escape for a palette color

CKT_REPO=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)
CKT_SETTINGS="${CKT_CONFIG_DIR:-$HOME/.config/custom-kitty-terminal}/settings.json"

_ckt_setting() { # key default allowed...
  local key=$1 def=$2 v; shift 2
  v=$(jq -r --arg k "$key" '.[$k] // empty' "$CKT_SETTINGS" 2>/dev/null)
  for a in "$@"; do [[ $v == "$a" ]] && { printf '%s' "$v"; return; }; done
  printf '%s' "$def"
}

ckt_lang() { _ckt_setting language en en pt; }
ckt_theme() { _ckt_setting theme fedora fedora catppuccin tokyo-night dracula gruvbox light noctalia; }

ckt_t() {
  local key=$1 lang v
  lang=$(ckt_lang)
  for l in "$lang" en; do
    v=$(jq -r --arg k "$key" '.[$k] // empty | if type == "array" then join("\n") else . end' "$CKT_REPO/i18n/$l.json" 2>/dev/null)
    [[ -n $v ]] && { printf '%s' "$v"; return; }
  done
  printf '%s' "$key"
}

_ckt_rgb() { # palette-key -> "r;g;b"
  local hex
  hex=$(jq -r --arg k "$1" '.[$k] // empty' "$CKT_REPO/themes/$(ckt_theme)/palette.json" 2>/dev/null)
  [[ $hex =~ ^#[0-9a-fA-F]{6}$ ]] || hex="#ffffff"
  printf '%d;%d;%d' "0x${hex:1:2}" "0x${hex:3:2}" "0x${hex:5:2}"
}

ckt_color() { printf '\e[38;2;%sm' "$(_ckt_rgb "$1")"; }
ckt_bg() { printf '\e[48;2;%sm' "$(_ckt_rgb "$1")"; }
