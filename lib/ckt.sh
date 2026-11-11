# Shell side of lib/ckt.py: reads the user's settings, translations and theme
# palette. Source it from bash; needs jq. Every lookup falls back to defaults.
#   ckt_lang          -> en | pt | zh
#   ckt_theme         -> fedora | catppuccin | ...
#   ckt_t <key>       -> translated text (English, then the key itself, as fallbacks)
#   ckt_color <name>  -> ANSI foreground escape for a palette color
#   ckt_bg <name>     -> ANSI background escape for a palette color
#   ckt_width <text>  -> screen columns of text (ANSI codes take none, CJK characters two)
#   ckt_fit <text> <n> -> text cut to n columns, ending in … when cut

CKT_REPO=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)
CKT_SETTINGS="${CKT_CONFIG_DIR:-$HOME/.config/custom-kitty-terminal}/settings.json"

_ckt_setting() { # key default allowed...
  local key=$1 def=$2 v; shift 2
  v=$(jq -r --arg k "$key" '.[$k] // empty' "$CKT_SETTINGS" 2>/dev/null)
  for a in "$@"; do [[ $v == "$a" ]] && { printf '%s' "$v"; return; }; done
  printf '%s' "$def"
}

ckt_lang() { _ckt_setting language en en pt zh; }
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

# East Asian wide characters (CJK, Hangul, full-width forms, most emoji) take two columns.
_ckt_wide() { # code point
  local c=$1
  (( (c >= 0x1100 && c <= 0x115F) || (c >= 0x2E80 && c <= 0x303E) || (c >= 0x3041 && c <= 0x33FF) ||
     (c >= 0x3400 && c <= 0x4DBF) || (c >= 0x4E00 && c <= 0x9FFF) || (c >= 0xA000 && c <= 0xA4CF) ||
     (c >= 0xAC00 && c <= 0xD7A3) || (c >= 0xF900 && c <= 0xFAFF) || (c >= 0xFE30 && c <= 0xFE4F) ||
     (c >= 0xFF00 && c <= 0xFF60) || (c >= 0xFFE0 && c <= 0xFFE6) || (c >= 0x1F300 && c <= 0x1F64F) ||
     (c >= 0x1F900 && c <= 0x1F9FF) || (c >= 0x20000 && c <= 0x3FFFD) ))
}

_ckt_cols() { # plain text -> columns
  local s=$1 n=0 i cp
  [[ $s == *[![:ascii:]]* ]] || { printf '%s' "${#s}"; return; }
  for ((i = 0; i < ${#s}; i++)); do
    printf -v cp '%d' "'${s:i:1}"
    if _ckt_wide "$cp"; then (( n += 2 )); else (( n += 1 )); fi
  done
  printf '%s' "$n"
}

ckt_width() { _ckt_cols "$(printf '%s' "$1" | sed $'s/\e\\[[0-9;]*m//g')"; }

ckt_fit() { # plain text, columns
  local s=$1 max=$2 out="" w=0 i c cp cw
  (( $(_ckt_cols "$s") <= max )) && { printf '%s' "$s"; return; }
  for ((i = 0; i < ${#s}; i++)); do
    c=${s:i:1}; printf -v cp '%d' "'$c"
    cw=1; _ckt_wide "$cp" && cw=2
    (( w + cw > max - 1 )) && break
    out+=$c; (( w += cw ))
  done
  printf '%s…' "$out"
}
