#!/usr/bin/env bash
# Status line do Claude Code em UMA linha que ocupa a largura do terminal:
#   esquerda: projeto · branch · worktree · modelo
#   direita:  barras de contexto, limite de 5h e limite semanal
# Se não couber, encurta (barras menores, sem horários) e, no limite, quebra em duas.
# Recebe o JSON da sessão em stdin (https://code.claude.com/docs/en/statusline).

input=$(cat)

# Cores (ANSI). Tons próximos do tema "fedora".
R=$'\e[0m'; DIM=$'\e[2m'; B=$'\e[1m'
BLUE=$'\e[38;2;81;162;218m'; MAG=$'\e[38;2;196;156;242m'; CYAN=$'\e[38;2;125;207;255m'
ORANGE=$'\e[38;2;255;158;100m'; GREEN=$'\e[38;2;158;206;106m'; YELLOW=$'\e[38;2;224;175;104m'; RED=$'\e[38;2;247;118;142m'

IFS=$'\t' read -r cwd proj model effort wt ctx h5 h5r d7 d7r < <(
  jq -r '[
    (.workspace.current_dir // .cwd // ""),
    (.workspace.project_dir // ""),
    (.model.display_name // ""),
    (.effort.level // ""),
    (.worktree.name // .workspace.git_worktree // ""),
    (.context_window.used_percentage // "" | tostring),
    (.rate_limits.five_hour.used_percentage // "" | tostring),
    (.rate_limits.five_hour.resets_at // "" | tostring),
    (.rate_limits.seven_day.used_percentage // "" | tostring),
    (.rate_limits.seven_day.resets_at // "" | tostring)
  ] | map(if . == "" then "-" else . end) | @tsv' <<<"$input"
)
for v in cwd proj model effort wt ctx h5 h5r d7 d7r; do [[ ${!v} == "-" ]] && printf -v "$v" ''; done

# Largura útil: o Claude Code passa COLUMNS; deixa 4 colunas de folga (a margem do Claude Code).
width=$(( ${COLUMNS:-120} - 4 ))
SEP=" ${DIM}·${R} "

# ---------- esquerda ----------
name=$(basename "${proj:-$cwd}")
left="${BLUE}${B}${name}${R}"
if [[ -n $proj && -n $cwd && $cwd != "$proj" && $cwd == "$proj"/* ]]; then
  left+="${DIM}/${cwd#"$proj"/}${R}"
fi

if [[ -n $cwd ]] && git -C "$cwd" rev-parse --is-inside-work-tree &>/dev/null; then
  g=(git --no-optional-locks -C "$cwd")
  br=$("${g[@]}" branch --show-current 2>/dev/null)
  [[ -z $br ]] && br="@$("${g[@]}" rev-parse --short HEAD 2>/dev/null)"
  dirty=""; [[ -n $("${g[@]}" status --porcelain 2>/dev/null | head -1) ]] && dirty="*"
  ab=""
  if counts=$("${g[@]}" rev-list --left-right --count '@{upstream}...HEAD' 2>/dev/null); then
    read -r behind ahead <<<"$counts"
    (( ahead > 0 )) && ab+=" ⇡${ahead}"
    (( behind > 0 )) && ab+=" ⇣${behind}"
  fi
  left+="${SEP}${MAG}⎇ ${br}${dirty}${ab}${R}"
fi

[[ -n $wt ]] && left+="${SEP}${CYAN}⊞ ${wt}${R}"

if [[ -n $model ]]; then
  left+="${SEP}${ORANGE}${model}"
  [[ -n $effort ]] && left+=" ${DIM}${effort}${R}${ORANGE}"
  left+="${R}"
fi

# ---------- direita ----------
color_for() {
  local p=${1%.*}
  if (( p >= 80 )); then printf '%s' "$RED"
  elif (( p >= 50 )); then printf '%s' "$YELLOW"
  else printf '%s' "$GREEN"; fi
}
bar() { # porcentagem células
  local p=${1%.*} cells=$2 filled i out=""
  (( p > 100 )) && p=100
  filled=$(( (p * cells + 50) / 100 ))
  for ((i = 0; i < cells; i++)); do
    if (( i < filled )); then out+="▰"; else out+="▱"; fi
  done
  printf '%s' "$out"
}
segment() { # rótulo porcentagem células reset
  local label=$1 pct=$2 cells=$3 reset=$4 c
  c=$(color_for "$pct")
  printf '%s%s%s ' "$DIM" "$label" "$R"
  (( cells > 0 )) && printf '%s%s%s ' "$c" "$(bar "$pct" "$cells")" "$R"
  printf '%s%s%%%s' "$c" "${pct%.*}" "$R"
  [[ -n $reset ]] && printf ' %s↻%s%s' "$DIM" "$reset" "$R"
}

r5=""; [[ -n $h5r ]] && r5=$(date -d "@${h5r%.*}" +%H:%M 2>/dev/null)
r7=""; [[ -n $d7r ]] && r7=$(LC_TIME=pt_BR.UTF-8 date -d "@${d7r%.*}" '+%a %H:%M' 2>/dev/null)

right_at() { # células mostrar_reset
  local cells=$1 resets=$2 parts=() out p
  [[ -n $ctx ]] && parts+=("$(segment ctx "$ctx" "$cells" "")")
  [[ -n $h5 ]] && parts+=("$(segment 5h "$h5" "$cells" "$( ((resets)) && printf '%s' "$r5")")")
  [[ -n $d7 ]] && parts+=("$(segment sem "$d7" "$cells" "$( ((resets)) && printf '%s' "$r7")")")
  (( ${#parts[@]} )) || return 0
  out="${parts[0]}"
  for p in "${parts[@]:1}"; do out+="  ${DIM}│${R}  $p"; done
  printf '%s' "$out"
}

visible() { # largura visível (sem códigos ANSI)
  local s
  s=$(printf '%s' "$1" | sed $'s/\e\\[[0-9;]*m//g')
  printf '%s' "${#s}"
}

lw=$(visible "$left")
# Tenta versões cada vez mais curtas da direita até caber na mesma linha.
for spec in "10 1" "8 1" "6 1" "6 0" "0 0"; do
  read -r cells resets <<<"$spec"
  right=$(right_at "$cells" "$resets")
  rw=$(visible "$right")
  if (( lw + rw + 3 <= width )); then
    pad=$(( width - lw - rw ))
    printf '%s%*s%s\n' "$left" "$pad" '' "$right"
    exit 0
  fi
done

# Não coube: duas linhas.
printf '%s\n' "$left"
[[ -n $right ]] && printf '%s\n' "$(right_at 8 1)"
