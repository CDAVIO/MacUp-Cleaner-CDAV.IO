#!/bin/bash
# MacUp — Terminal look: black, white, grey and one yellow accent.
# Bash 3.2 compatible (the bash that ships with macOS).
# shellcheck disable=SC2059,SC2034  # colours in printf formats; H_* results are read by other files

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ] && [ "${MACUP_COLOR:-1}" != "0" ]; then
  C_Y=$'\033[38;5;220m'   # yellow #ffd905
  C_B=$'\033[1m'          # bold white
  C_D=$'\033[38;5;245m'   # grey
  C_R=$'\033[0m'
else
  C_Y=""; C_B=""; C_D=""; C_R=""
fi

UI_WIDTH=62

# Display width of a string: characters, with Korean/Chinese counted double.
ui_width() {
  local s="$1" chars bytes
  chars=${#s}
  bytes=$(LC_ALL=C; printf '%s' "$s" | wc -c | tr -d ' ')
  case "${MACUP_LANG_CODE:-en}" in
    ko|zh) printf '%s' $(( chars + (bytes - chars) / 2 )) ;;
    *) printf '%s' "$chars" ;;
  esac
}

# ui_pad TEXT WIDTH → text followed by spaces up to WIDTH columns.
ui_pad() {
  local w; w=$(ui_width "$1")
  printf '%s' "$1"
  [ "$w" -lt "$2" ] && printf '%*s' $(( $2 - w )) ''
  return 0
}

ui_line() { printf "  ${C_D}%s${C_R}\n" "$(printf '─%.0s' $(seq 1 "$UI_WIDTH"))"; }

ui_logo() {
  printf "\n  ${C_Y}✦${C_R} ${C_B}MacUp${C_R}  ${C_D}%s${C_R}\n" "$1"
  ui_line
}

ui_title() {
  printf "\n  ${C_Y}%s${C_R}  ${C_B}%s${C_R}\n" "${2:-■}" "$1"
  ui_line
}

ui_note() { printf "  ${C_D}%s${C_R}\n" "$1"; }

# ui_row "Label" "Value" [ok|warn|bad|info]
ui_row() {
  local mark="" status="${3:-}"
  case "$status" in
    ok)   mark="${C_B}✓${C_R}" ;;
    warn) mark="${C_Y}!${C_R}" ;;
    bad)  mark="${C_Y}✕${C_R}" ;;
    info) mark="${C_D}·${C_R}" ;;
  esac
  [ -z "$mark" ] && mark=" "
  printf "  %b  %s %b\n" "$mark" "$(ui_pad "$1" 28)" "$2"
}

# ui_bar PERCENT [WIDTH] → ████████░░░░ (yellow fill, grey track)
ui_bar() {
  local pct="${1:-0}" width="${2:-24}" fill i on="" off=""
  case "$pct" in ''|*[!0-9]*) pct=0 ;; esac
  [ "$pct" -gt 100 ] && pct=100
  fill=$(( pct * width / 100 ))
  for ((i = 0; i < width; i++)); do
    if [ "$i" -lt "$fill" ]; then on="${on}█"; else off="${off}░"; fi
  done
  printf "%s%s%s%s%s" "$C_Y" "$on" "$C_D" "$off" "$C_R"
}

# ui_score LABEL SCORE → "Storage   ████████░░  82%"
ui_score() {
  local label="$1" score="$2"
  if [ -z "$score" ]; then
    printf "  %s ${C_D}%s${C_R}\n" "$(ui_pad "$label" 22)" "—"
  else
    printf "  %s %s  ${C_B}%3s%%${C_R}\n" "$(ui_pad "$label" 22)" "$(ui_bar "$score" 24)" "$score"
  fi
}

# ui_ask "Question" default → reply in $REPLY (default when Enter or no TTY)
ui_ask() {
  local prompt="$1" def="${2:-}"
  if [ ! -t 0 ]; then REPLY="$def"; return 0; fi
  printf "\n  ${C_Y}›${C_R} %s " "$prompt"
  IFS= read -r REPLY || REPLY=""
  [ -z "$REPLY" ] && REPLY="$def"
  return 0
}

# ui_yes "Question" [y|n] → 0 for yes
ui_yes() {
  local def="${2:-n}" hint="[y/N]"
  [ "$def" = "y" ] && hint="[Y/n]"
  [ "${MACUP_YES:-0}" = "1" ] && return 0
  ui_ask "$1 $hint" "$def"
  case "$REPLY" in [YyDdJjOoSs]*|是*|네*) return 0 ;; esac
  return 1
}

# ui_spin "Message" command args… → runs the command with a spinner, keeps its exit code.
ui_spin() {
  local msg="$1"; shift
  if [ ! -t 1 ]; then "$@"; return $?; fi
  "$@" &
  local pid=$! frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏' i=0
  while kill -0 "$pid" 2>/dev/null; do
    printf "\r  ${C_Y}%s${C_R} %s" "${frames:$((i % 10)):1}" "$msg"
    i=$((i + 1))
    sleep 0.1
  done
  wait "$pid"; local rc=$?
  printf "\r\033[K"
  return $rc
}

ui_pause() {
  [ -t 0 ] || return 0
  printf "\n  ${C_D}%s${C_R}" "$1"
  IFS= read -r _ || true
}

# Human-readable size from bytes (decimal, like Finder).
ui_size() {
  awk -v b="${1:-0}" 'BEGIN {
    split("B KB MB GB TB", u, " "); i = 1
    while (b >= 1000 && i < 5) { b /= 1000; i++ }
    if (i == 1) printf "%d %s", b, u[i]; else printf "%.1f %s", b, u[i]
  }'
}
