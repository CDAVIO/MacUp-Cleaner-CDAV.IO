#!/bin/bash
# MacUp installer — free & open source · https://github.com/CDAVIO/MacUp-Cleaner-CDAV.IO
#
#   curl -fsSL https://raw.githubusercontent.com/CDAVIO/MacUp-Cleaner-CDAV.IO/main/install.sh | bash
#
# What it does: copies MacUp into ~/.macup and adds the `macup` command.
# No admin password, nothing runs in the background, nothing is sent anywhere.
# Remove it any time with: macup uninstall
#
# Everything lives inside main(), called on the last line, so a partly
# downloaded script never runs.
set -euo pipefail

MACUP_REPO="CDAVIO/MacUp-Cleaner-CDAV.IO"
MACUP_BRANCH="${MACUP_BRANCH:-main}"
# Files and folders that make up an installed MacUp (nothing else is copied).
MACUP_PARTS="macup VERSION LICENSE THIRD_PARTY_NOTICES.md lib engine bin"

say()  { printf '  %s\n' "$*"; }
ok()   { printf '  \033[38;5;220m✓\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✕\033[0m %s\n' "$*" >&2; exit 1; }

# fetch_source DIR → prints the folder that holds the MacUp sources.
fetch_source() {
  local tmp="$1" src
  if [ -n "${MACUP_SOURCE:-}" ]; then
    # Local folder (used by the tests and for offline installs).
    [ -d "$MACUP_SOURCE" ] || fail "MACUP_SOURCE is not a folder: $MACUP_SOURCE"
    printf '%s' "$MACUP_SOURCE"
    return
  fi
  command -v curl >/dev/null 2>&1 || fail "curl is missing."
  curl -fsSL --retry 2 --connect-timeout 15 \
    "https://codeload.github.com/$MACUP_REPO/tar.gz/refs/heads/$MACUP_BRANCH" \
    -o "$tmp/macup.tar.gz" || fail "Could not download MacUp from GitHub. Check your internet connection."
  mkdir "$tmp/src"
  tar -xzf "$tmp/macup.tar.gz" -C "$tmp/src" || fail "The download looks damaged. Please try again."
  src="$(find "$tmp/src" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  [ -n "$src" ] || fail "The download looks empty. Please try again."
  printf '%s' "$src"
}

# is_macup_dir DIR → true if DIR is an earlier MacUp install.
is_macup_dir() { [ -f "$1/macup" ] && [ -f "$1/VERSION" ] && [ -d "$1/lib" ]; }

# pick_bin_dir → a folder on PATH where we can add the `macup` link without a password.
pick_bin_dir() {
  local d
  if [ -n "${MACUP_BIN_DIR:-}" ]; then printf '%s' "$MACUP_BIN_DIR"; return; fi
  for d in /opt/homebrew/bin /usr/local/bin; do
    if [ -d "$d" ] && [ -w "$d" ]; then
      case ":$PATH:" in *":$d:"*) printf '%s' "$d"; return ;; esac
    fi
  done
  printf '%s' "$HOME/.local/bin"
}

# add_to_path DIR → adds DIR to PATH for new Terminal windows (only if missing).
add_to_path() {
  local dir="$1" line rc shown
  case ":$PATH:" in *":$dir:"*) return 1 ;; esac
  case "$dir" in
    "$HOME"/*) shown="\$HOME/${dir#"$HOME"/}" ;;
    *)         shown="$dir" ;;
  esac
  line="export PATH=\"$shown:\$PATH\" # added by MacUp"
  case "${SHELL:-/bin/zsh}" in
    */bash) rc="$HOME/.bash_profile" ;;
    *)      rc="$HOME/.zprofile" ;;
  esac
  if ! grep -qs '# added by MacUp' "$rc"; then
    printf '\n%s\n' "$line" >> "$rc"
  fi
  return 0
}

main() {
  local dest="$HOME/.macup" tmp src part new old bin link version path_added=0

  [ -n "${HOME:-}" ] && [ -d "$HOME" ] || fail "HOME is not set."
  [ "$(uname -s)" = "Darwin" ] || fail "MacUp runs on macOS only."
  local major; major="$(sw_vers -productVersion 2>/dev/null | cut -d. -f1)"
  [ "${major:-0}" -ge 13 ] 2>/dev/null || fail "MacUp needs macOS 13 Ventura or newer."
  [ "$(id -u)" -ne 0 ] || fail "Please run the installer without sudo."

  printf '\n  \033[1m✦ MacUp\033[0m  installer\n\n'

  if [ -e "$dest" ] && ! is_macup_dir "$dest"; then
    fail "$dest already exists and is not MacUp — move it away, then run the installer again."
  fi

  tmp="$(mktemp -d "${TMPDIR:-/tmp}/macup-install.XXXXXX")"
  # shellcheck disable=SC2064
  trap "rm -rf '$tmp'" EXIT

  say "Downloading MacUp…"
  src="$(fetch_source "$tmp")"
  for part in macup VERSION lib/ui.sh lib/lang/en.sh engine/clean_mac.sh; do
    [ -e "$src/$part" ] || fail "The download is incomplete ($part missing). Please try again."
  done
  version="$(tr -d '[:space:]' < "$src/VERSION")"

  # Build the new copy next to the old one, then swap them in one step.
  new="$HOME/.macup.new.$$"
  old="$HOME/.macup.old.$$"
  rm -rf "$new" "$old"
  mkdir "$new"
  for part in $MACUP_PARTS; do
    [ -e "$src/$part" ] && cp -R "$src/$part" "$new/"
  done
  chmod 755 "$new/macup" "$new/engine/clean_mac.sh"
  [ -f "$new/bin/macup-pdf" ] && chmod 755 "$new/bin/macup-pdf"

  [ -e "$dest" ] && mv "$dest" "$old"
  mv "$new" "$dest"
  rm -rf "$old"
  ok "Installed MacUp $version in ~/.macup"

  bin="$(pick_bin_dir)"
  mkdir -p "$bin"
  link="$bin/macup"
  if [ -e "$link" ] || [ -L "$link" ]; then
    if [ -L "$link" ] && [ "$(readlink "$link")" = "$dest/macup" ]; then
      :
    else
      fail "$link already exists and is not MacUp — remove it, then run the installer again."
    fi
  else
    ln -s "$dest/macup" "$link"
  fi
  ok "Added the macup command ($link)"

  if add_to_path "$bin"; then path_added=1; fi

  printf '\n  Start it with:\n\n'
  if [ "$path_added" = "1" ]; then
    printf '    \033[38;5;220m%s\033[0m\n\n' "$link"
    say "(in new Terminal windows just type: macup)"
  else
    printf '    \033[38;5;220mmacup\033[0m\n'
  fi
  printf '\n'
}

main "$@"
