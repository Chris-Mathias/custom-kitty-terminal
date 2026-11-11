#!/usr/bin/env bash
# Ctrl+W confirmation box (opened by close_tab.py as an overlay on the tab).
# Usage: close-tab-dialog.sh tab:<id>|window:<id> <running program>...
target=$1; shift
kind=${target%%:*}; target_id=${target#*:}
if [[ $kind == window ]]; then question="Fechar esta sessão?"; else question="Fechar esta aba?"; fi

R=$'\e[0m'; B=$'\e[1m'; DIM=$'\e[38;2;139;138;144m'
BLUE=$'\e[38;2;81;162;218m'; YELLOW=$'\e[38;2;224;175;104m'; WHITE=$'\e[38;2;255;255;255m'
BG=$'\e[48;2;28;28;31m'; BOX=$'\e[48;2;38;38;44m'; BORDER=$'\e[38;2;60;110;180m'
KEY_BLUE=$'\e[48;2;60;110;180m\e[38;2;255;255;255m'; KEY_GRAY=$'\e[48;2;58;58;66m\e[38;2;220;220;220m'

cols=$(tput cols); lines=$(tput lines)
width=54; (( width > cols - 4 )) && width=$(( cols - 4 ))
inner=$(( width - 2 ))

rows=()
rows+=("")
rows+=("  ${B}${WHITE}${question}${R}${BOX}")
rows+=("")
rows+=("  ${DIM}Ainda está rodando:${R}${BOX}")
for p in "$@"; do
  (( ${#p} > inner - 6 )) && p="${p:0:inner-7}…"
  rows+=("   ${YELLOW}●${R}${BOX} ${WHITE}${p}${R}${BOX}")
done
rows+=("")
rows+=("  ${KEY_BLUE} Enter ${R}${BOX} ${WHITE}fechar${R}${BOX}     ${KEY_GRAY} Esc ${R}${BOX} ${DIM}cancelar${R}${BOX}")
rows+=("")

visible() { local s; s=$(printf '%s' "$1" | sed $'s/\e\\[[0-9;]*m//g'); printf '%s' "${#s}"; }

height=$(( ${#rows[@]} + 2 ))
top=$(( (lines - height) / 2 )); (( top < 0 )) && top=0
left=$(( (cols - width) / 2 )); (( left < 0 )) && left=0
pad=$(printf '%*s' "$left" '')

draw() {
  printf '\e[?25l%s\e[2J\e[H' "$BG"
  for ((i = 0; i < top; i++)); do printf '\n'; done
  printf '%s%s%s╭%s╮%s\n' "$pad" "$BOX" "$BORDER" "$(printf '─%.0s' $(seq 1 "$inner"))" "$R$BG"
  for l in "${rows[@]}"; do
    rest=$(( inner - $(visible "$l") ))
    (( rest < 0 )) && rest=0
    printf '%s%s%s│%s%s%*s%s│%s\n' "$pad" "$BOX" "$BORDER" "$R$BOX" "$l" "$rest" '' "$BORDER" "$R$BG"
  done
  printf '%s%s%s╰%s╯%s' "$pad" "$BOX" "$BORDER" "$(printf '─%.0s' $(seq 1 "$inner"))" "$R$BG"
}

trap 'printf "\e[?25h%s" "$R"' EXIT
draw
while IFS= read -rsn1 key; do
  case "$key" in
    ""|s|S|y|Y)
      if [[ $kind == window ]]; then
        kitten @ close-window --match "id:$target_id" >/dev/null 2>&1
      else
        kitten @ close-tab --match "id:$target_id" >/dev/null 2>&1
      fi
      exit 0 ;;
    $'\e'|n|N|q|Q)
      exit 0 ;;
  esac
done
