#!/usr/bin/env bash
# Subagent lines (the area below the prompt) for Claude Code.
# Shows, per subagent: name · what it's doing · branch/worktree it works in
# and, on the right, time and tokens. Reads JSON with `tasks` and prints one
# JSON line {"id","content"} per subagent (https://code.claude.com/docs/en/statusline).

input=$(cat)

source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../lib/ckt.sh"
R=$'\e[0m'; DIM=$'\e[2m'; B=$'\e[1m'
MAG=$(ckt_color magenta); CYAN=$(ckt_color cyan)
CHANGES=$(ckt_t subagent.changes)

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

jq -r --arg fallback "$(ckt_t subagent.fallback_name)" '.tasks[]? | [
  .id,
  (.name // .agentType // .type // $fallback),
  (.label // .description // ""),
  (.cwd // ""),
  (.startTime // 0 | tostring),
  (.tokenCount // 0 | tostring),
  (.status // "")
] | map(if . == "" then "-" else . end) | @tsv' <<<"$input" |
while IFS=$'\t' read -r id name label cwd start tokens status; do
  [[ $label == "-" ]] && label=""
  [[ $cwd == "-" ]] && cwd=""

  # Where the subagent works: only shown when it's another directory (e.g. an isolated worktree)
  where=""
  if [[ -n $cwd && $cwd != "$session_cwd" ]] && git -C "$cwd" rev-parse --is-inside-work-tree &>/dev/null; then
    br=$(git --no-optional-locks -C "$cwd" branch --show-current 2>/dev/null)
    [[ -z $br ]] && br="@$(git --no-optional-locks -C "$cwd" rev-parse --short HEAD 2>/dev/null)"
    # worktree-agent-a558ed42b2178b89f -> worktree-agent-a558ed
    br=$(sed -E 's/(agent-[0-9a-f]{6})[0-9a-f]+/\1/' <<<"$br")
    n=$(git --no-optional-locks -C "$cwd" status --porcelain 2>/dev/null | wc -l)
    where="${MAG}⎇ ${br}${R}"
    (( n > 0 )) && where+=" ${DIM}${n} ${CHANGES}${R}"
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
