#!/usr/bin/env bash
# Linhas dos subagentes (o painel embaixo do prompt) para o Claude Code.
# Mostra, por subagente: nome · o que está fazendo · branch/worktree onde trabalha
# e, à direita, tempo e tokens. Recebe um JSON com `tasks` e devolve uma linha
# JSON {"id","content"} por subagente (https://code.claude.com/docs/en/statusline).

input=$(cat)

R=$'\e[0m'; DIM=$'\e[2m'; B=$'\e[1m'
MAG=$'\e[38;2;196;156;242m'; CYAN=$'\e[38;2;125;207;255m'

session_cwd=$(jq -r '.cwd // ""' <<<"$input")
cols=$(jq -r '.columns // 100' <<<"$input")
width=$(( cols - 2 ))
now_ms=$(( $(date +%s) * 1000 ))

visible() { local s; s=$(printf '%s' "$1" | sed $'s/\e\\[[0-9;]*m//g'); printf '%s' "${#s}"; }
short_tokens() { # 495900 -> 496k
  local n=${1:-0}
  if (( n >= 1000000 )); then printf '%d.%dM' $((n / 1000000)) $(( (n % 1000000) / 100000 ))
  elif (( n >= 1000 )); then printf '%dk' $(( (n + 500) / 1000 ))
  else printf '%d' "$n"; fi
}
short_time() { # ms -> 42m / 1h05m / 12s
  local s=$(( ${1:-0} / 1000 ))
  if (( s >= 3600 )); then printf '%dh%02dm' $((s / 3600)) $(( (s % 3600) / 60 ))
  elif (( s >= 60 )); then printf '%dm' $((s / 60))
  else printf '%ds' "$s"; fi
}

jq -r '.tasks[]? | [
  .id,
  (.name // .agentType // .type // "agente"),
  (.label // .description // ""),
  (.cwd // ""),
  (.startTime // 0 | tostring),
  (.tokenCount // 0 | tostring),
  (.status // "")
] | map(if . == "" then "-" else . end) | @tsv' <<<"$input" |
while IFS=$'\t' read -r id name label cwd start tokens status; do
  [[ $label == "-" ]] && label=""
  [[ $cwd == "-" ]] && cwd=""

  # Onde o subagente trabalha: só mostra quando é outro diretório (ex.: worktree isolada)
  where=""
  if [[ -n $cwd && $cwd != "$session_cwd" ]] && git -C "$cwd" rev-parse --is-inside-work-tree &>/dev/null; then
    br=$(git --no-optional-locks -C "$cwd" branch --show-current 2>/dev/null)
    [[ -z $br ]] && br="@$(git --no-optional-locks -C "$cwd" rev-parse --short HEAD 2>/dev/null)"
    # worktree-agent-a558ed42b2178b89f -> worktree-agent-a558ed
    br=$(sed -E 's/(agent-[0-9a-f]{6})[0-9a-f]+/\1/' <<<"$br")
    n=$(git --no-optional-locks -C "$cwd" status --porcelain 2>/dev/null | wc -l)
    where="${MAG}⎇ ${br}${R}"
    (( n > 0 )) && where+=" ${DIM}${n} alt.${R}"
  fi

  right=""
  if [[ $start != "-" && $start != 0 ]]; then right+="$(short_time $(( now_ms - ${start%.*} )))"; fi
  if [[ $tokens != "-" && $tokens != 0 ]]; then right+="${right:+ · }↓ $(short_tokens "${tokens%.*}")"; fi
  right="${DIM}${right}${R}"

  left="${B}${name}${R}"
  [[ -n $where ]] && left+="  ${where}"
  rest=$(( width - $(visible "$left") - $(visible "$right") - 4 ))
  if [[ -n $label ]] && (( rest > 8 )); then
    (( ${#label} > rest )) && label="${label:0:rest-1}…"
    left+="  ${label}"
  fi

  pad=$(( width - $(visible "$left") - $(visible "$right") ))
  (( pad < 2 )) && pad=2
  content=$(printf '%s%*s%s' "$left" "$pad" '' "$right")
  jq -cn --arg id "$id" --arg content "$content" '{id: $id, content: $content}'
done
