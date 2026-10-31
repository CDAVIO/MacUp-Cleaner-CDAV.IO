#!/bin/bash
# MacUp — languages: en, ro, de, it, fr, ko, zh.
# Every language file defines S_<key>='…' strings; English loads first, so a
# missing translation falls back to English instead of breaking.
# shellcheck disable=SC2059,SC2034  # colours in printf formats; H_* results are read by other files

MACUP_LANGS="en ro de it fr ko zh"

i18n_detect() {
  local pick="${MACUP_LANG:-}"
  if [ -z "$pick" ]; then
    pick=$(defaults read -g AppleLanguages 2>/dev/null | sed -n '2p' | tr -d ' ",')
    [ -z "$pick" ] && pick="${LANG:-en}"
  fi
  pick=$(printf '%s' "$pick" | cut -c1-2 | tr '[:upper:]' '[:lower:]')
  case " $MACUP_LANGS " in *" $pick "*) ;; *) pick="en" ;; esac
  printf '%s' "$pick"
}

i18n_load() {
  MACUP_LANG_CODE="${1:-en}"
  # shellcheck source=lang/en.sh
  . "$MACUP_ROOT/lib/lang/en.sh"
  if [ "$MACUP_LANG_CODE" != "en" ] && [ -f "$MACUP_ROOT/lib/lang/$MACUP_LANG_CODE.sh" ]; then
    # shellcheck disable=SC1090
    . "$MACUP_ROOT/lib/lang/$MACUP_LANG_CODE.sh"
  fi
}

# t KEY [ARG1] [ARG2] [ARG3] → translated text with {1} {2} {3} filled in.
t() {
  local var="S_$1" text
  text="${!var:-$1}"
  [ $# -ge 2 ] && text="${text//\{1\}/$2}"
  [ $# -ge 3 ] && text="${text//\{2\}/$3}"
  [ $# -ge 4 ] && text="${text//\{3\}/$4}"
  printf '%s' "$text"
}
