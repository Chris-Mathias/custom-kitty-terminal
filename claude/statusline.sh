#!/usr/bin/env bash
# Claude Code status line on ONE line spanning the terminal width:
#   left:  project · branch · worktree · model
#   right: context, 5h limit and weekly limit bars
# If it doesn't fit, it shortens (smaller bars, no times) and, at worst, wraps into two lines.
# Reads the session JSON on stdin (https://code.claude.com/docs/en/statusline).

input=$(cat)

# Language and colors come from the settings menu (ct config).
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../lib/ckt.sh"
R=$'\e[0m'; DIM=$'\e[2m'; B=$'\e[1m'
BLUE=$(ckt_color accent); MAG=$(ckt_color magenta); CYAN=$(ckt_color cyan)
ORANGE=$(ckt_color orange); GREEN=$(ckt_color green); YELLOW=$(ckt_color yellow); RED=$(ckt_color red)
WEEK=$(ckt_t status.week)
if [[ $(ckt_lang) == pt ]]; then TIME_LOCALE=pt_BR.UTF-8; else TIME_LOCALE=en_US.UTF-8; fi

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

# Usable width: Claude Code passes COLUMNS; leave 4 spare columns (Claude Code's margin).
width=$(( ${COLUMNS:-120} - 4 ))
SEP=" ${DIM}·${R} "

# ---------- left ----------
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

# ---------- right ----------
color_for() {
  local p=${1%.*}
  if (( p >= 80 )); then printf '%s' "$RED"
  elif (( p >= 50 )); then printf '%s' "$YELLOW"
  else printf '%s' "$GREEN"; fi
}
bar() { # percent cells
  local p=${1%.*} cells=$2 filled i out=""
  (( p > 100 )) && p=100
  filled=$(( (p * cells + 50) / 100 ))
  for ((i = 0; i < cells; i++)); do
    if (( i < filled )); then out+="▰"; else out+="▱"; fi
  done
  printf '%s' "$out"
}
segment() { # label percent cells reset
  local label=$1 pct=$2 cells=$3 reset=$4 c
  c=$(color_for "$pct")
  printf '%s%s%s ' "$DIM" "$label" "$R"
  (( cells > 0 )) && printf '%s%s%s ' "$c" "$(bar "$pct" "$cells")" "$R"
  printf '%s%s%%%s' "$c" "${pct%.*}" "$R"
  [[ -n $reset ]] && printf ' %s↻%s%s' "$DIM" "$reset" "$R"
}

r5=""; [[ -n $h5r ]] && r5=$(date -d "@${h5r%.*}" +%H:%M 2>/dev/null)
r7=""; [[ -n $d7r ]] && r7=$(LC_TIME=$TIME_LOCALE date -d "@${d7r%.*}" '+%a %H:%M' 2>/dev/null)

right_at() { # cells show_reset
  local cells=$1 resets=$2 parts=() out p
  [[ -n $ctx ]] && parts+=("$(segment ctx "$ctx" "$cells" "")")
  [[ -n $h5 ]] && parts+=("$(segment 5h "$h5" "$cells" "$( ((resets)) && printf '%s' "$r5")")")
  [[ -n $d7 ]] && parts+=("$(segment "$WEEK" "$d7" "$cells" "$( ((resets)) && printf '%s' "$r7")")")
  (( ${#parts[@]} )) || return 0
  out="${parts[0]}"
  for p in "${parts[@]:1}"; do out+="  ${DIM}│${R}  $p"; done
  printf '%s' "$out"
}

visible() { # visible width (without ANSI codes)
  local s
  s=$(printf '%s' "$1" | sed $'s/\e\\[[0-9;]*m//g')
  printf '%s' "${#s}"
}

lw=$(visible "$left")
# Tries ever shorter versions of the right side until it fits on the same line.
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

# Didn't fit: two lines.
printf '%s\n' "$left"
[[ -n $right ]] && printf '%s\n' "$(right_at 8 1)"
