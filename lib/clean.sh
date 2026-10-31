#!/bin/bash
# MacUp — Smart Clean. Only rebuildable caches, always moved to the Trash.
# The cleaning itself is done by engine/clean_mac.sh in Trash-only mode,
# which refuses anything that would delete permanently.
# shellcheck disable=SC2059,SC2034  # colours in printf formats; H_* results are read by other files

# Offered categories, in display order. The first four are pre-selected.
CLEAN_IDS="user_cache browser_cache logs diagnostic_reports developer browser_history saved_app_state"
CLEAN_RECOMMENDED="user_cache browser_cache logs diagnostic_reports"
# Developer caches MacUp offers: only download/build caches that tools rebuild
# by themselves. Left out on purpose: anything that deletes for good (Docker
# prune, simulator deletes, brew cleanup), downloaded AI models, Xcode
# archives, broken links, the live system font cache, the Maven local
# repository (may hold your own builds) and the pub cache (global tools).
CLEAN_DEV_SAFE=" derived_data xcode_products xcode_previews xcode_logs coresim_caches simulator_logs device_support swift_pm_cache cocoapods_cache carthage_cache brew_cache npm_cache pnpm_cache yarn_cache bun_cache deno_cache pip_cache uv_cache poetry_cache conda_pkgs cargo_registry go_modules gradle_cache gradle_wrapper sbt_ivy_cache composer_cache bazel_cache playwright_cache puppeteer_cache prisma_cache jetbrains_cache "

engine() {
  FORCE_RM=0 TEST_MODE=0 APPLE_CLEANUP_TRASH_ONLY=1 APPLE_CLEANUP_FORCE_MANUAL_TRASH=1 APPLE_CLEANUP_LANG=en \
    bash "$MACUP_ROOT/engine/clean_mac.sh" "$@"
}

# clean_scan DIR → one JSON file per category, scanned in parallel (read-only).
clean_scan() {
  local dir="$1" id
  mkdir -p "$dir"
  for id in $CLEAN_IDS; do
    engine --scan-category-json "$id" > "$dir/$id.json" 2>/dev/null &
  done
  wait
}

# Safe developer sub-items with something in them: "id size" lines.
clean_dev_items() {
  local f="$1/developer.json" i=0 id size
  while :; do
    id=$(pj "$f" "category.subitems.$i.id")
    [ -z "$id" ] && break
    size=$(pj "$f" "category.subitems.$i.size_bytes")
    case "$CLEAN_DEV_SAFE" in *" $id "*)
      case "$size" in ''|*[!0-9]*) size=0 ;; esac
      [ "$size" -gt 0 ] && printf '%s %s\n' "$id" "$size" ;;
    esac
    i=$((i + 1))
  done
}

clean_size() {
  local dir="$1" id="$2" size
  if [ "$id" = "developer" ]; then
    clean_dev_items "$dir" | awk '{ s += $2 } END { printf "%d", s }'
    return
  fi
  size=$(pj "$dir/$id.json" category.size_bytes)
  case "$size" in ''|*[!0-9]*) size=0 ;; esac
  printf '%s' "$size"
}

clean_total() {
  local dir="$1" id total=0 s
  for id in $CLEAN_RECOMMENDED developer; do
    s=$(clean_size "$dir" "$id"); total=$((total + s))
  done
  printf '%s' "$total"
}

clean_label() {
  case "$1" in
    user_cache) t cat_app_caches ;;
    browser_cache) t cat_browser_caches ;;
    logs) t cat_logs ;;
    diagnostic_reports) t cat_reports ;;
    developer) t cat_developer ;;
    browser_history) t cat_history ;;
    saved_app_state) t cat_saved_state ;;
  esac
}

clean_hint() {
  case "$1" in
    user_cache|browser_cache) t hint_rebuilds ;;
    developer) t hint_developer ;;
    browser_history) t hint_history ;;
    saved_app_state) t hint_saved_state ;;
    *) t hint_safe ;;
  esac
}

running_browsers() {
  local list name out=""
  list=$(lsappinfo list 2>/dev/null)
  for name in "com.apple.Safari:Safari" "com.google.Chrome:Chrome" "com.brave.Browser:Brave" \
              "com.microsoft.edgemac:Edge" "company.thebrowser.Browser:Arc" \
              "com.vivaldi.Vivaldi:Vivaldi" "com.operasoftware.Opera:Opera"; do
    case "$list" in *"\"${name%%:*}\""*) out="${out}${out:+, }${name#*:}" ;; esac
  done
  printf '%s' "$out"
}

# clean_run "id id …" DRY(0/1) DIR → engine JSON result in DIR/result.json
clean_run() {
  local ids="$1" dry="$2" dir="$3" csv dev
  csv=$(printf '%s' "$ids" | tr ' ' ',' | sed 's/^,*//; s/,*$//')
  dev=$(clean_dev_items "$dir" | awk '{print $1}' | paste -sd, -)
  if [ "$dry" = "1" ]; then
    APPLE_CLEANUP_DRYRUN=1 engine --clean-ids-json "$csv" ${dev:+--developer-sub "$dev"} > "$dir/result.json" 2>/dev/null
  else
    engine --clean-ids-json "$csv" ${dev:+--developer-sub "$dev"} > "$dir/result.json" 2>/dev/null
  fi
  return 0
}

cmd_clean() {
  macup_tmp
  local dir="$MACUP_TMP/scan" id n i size total sel="" choice dry=0
  ui_title "$(t clean_title)" "1"
  ui_note "$(t clean_intro_1)"
  ui_note "$(t clean_intro_2)"
  echo
  ui_spin "$(t scanning)" clean_scan "$dir"

  # Pre-select the recommended categories that have something to clean.
  for id in $CLEAN_RECOMMENDED; do
    [ "$(clean_size "$dir" "$id")" -gt 0 ] && sel="$sel $id "
  done

  while :; do
    echo
    n=0; total=0
    for id in $CLEAN_IDS; do
      n=$((n + 1))
      size=$(clean_size "$dir" "$id")
      local box="  "
      case "$sel" in *" $id "*) box="${C_Y}✓${C_R} "; total=$((total + size)) ;; esac
      if [ "$size" -gt 0 ]; then
        printf "  ${C_D}%2s${C_R}  %b %s ${C_B}%9s${C_R}  ${C_D}%s${C_R}\n" "$n" "$box" "$(ui_pad "$(clean_label "$id")" 26)" "$(ui_size "$size")" "$(clean_hint "$id")"
      else
        printf "  ${C_D}%2s     %s %9s${C_R}\n" "$n" "$(ui_pad "$(clean_label "$id")" 26)" "—"
      fi
    done
    ui_line
    printf "  %s ${C_Y}${C_B}%s${C_R}  ${C_D}%s${C_R}\n" "$(t selected)" "$(ui_size "$total")" "$(t goes_to_trash)"

    if [ ! -t 0 ] && [ "${MACUP_YES:-0}" != "1" ]; then
      echo; ui_note "$(t noninteractive_preview)"; dry=1; break
    fi
    [ "${MACUP_YES:-0}" = "1" ] && break
    ui_ask "$(t clean_prompt)" ""
    choice=$(printf '%s' "$REPLY" | tr '[:upper:]' '[:lower:]')
    case "$choice" in
      "") break ;;
      p) dry=1; break ;;
      q) echo; ui_note "$(t cancelled)"; return 0 ;;
      *)
        for i in $choice; do
          case "$i" in ''|*[!0-9]*) continue ;; esac
          # shellcheck disable=SC2086  # CLEAN_IDS is a space-separated list on purpose
          id=$(printf '%s\n' $CLEAN_IDS | sed -n "${i}p")
          [ -z "$id" ] && continue
          case "$sel" in *" $id "*) sel=$(printf '%s' "$sel" | sed "s/ $id //") ;; *) sel="$sel $id " ;; esac
        done ;;
    esac
  done

  sel=$(printf '%s' "$sel" | xargs)
  if [ -z "$sel" ]; then echo; ui_note "$(t nothing_selected)"; return 0; fi

  case " $sel " in *" browser_history "*)
    local open; open=$(running_browsers)
    if [ -n "$open" ]; then
      echo; ui_row "$(t cat_history)" "$(t browsers_open "$open")" warn
      if [ "$dry" = "0" ] && ui_yes "$(t quit_browsers_q)" n; then
        osascript -l JavaScript -e 'ObjC.import("AppKit"); ["com.apple.Safari","com.google.Chrome","com.brave.Browser","com.microsoft.edgemac","company.thebrowser.Browser","com.vivaldi.Vivaldi","com.operasoftware.Opera"].forEach(function(id){ var a=$.NSRunningApplication.runningApplicationsWithBundleIdentifier(id); for (var i=0;i<a.count;i++) a.objectAtIndex(i).terminate; });' >/dev/null 2>&1
        sleep 3
      fi
    fi ;;
  esac

  echo
  if [ "$dry" = "1" ]; then
    ui_spin "$(t previewing)" clean_run "$sel" 1 "$dir"
  else
    ui_spin "$(t cleaning)" clean_run "$sel" 0 "$dir"
  fi
  clean_report "$dir/result.json" "$dry" "$sel"
}

clean_report() {
  local f="$1" dry="$2" sel="$3" i cat status bytes msg moved
  moved=$(pj "$f" estimated_bytes); case "$moved" in ''|*[!0-9]*) moved=0 ;; esac
  i=0
  while :; do
    cat=$(pj "$f" "details.$i.category"); [ -z "$cat" ] && break
    status=$(pj "$f" "details.$i.status")
    case "$status" in
      error|skipped) ui_row "$(clean_label "$cat")" "$(t status_skipped)" warn ;;
      partial) ui_row "$(clean_label "$cat")" "$( [ "$dry" = "1" ] && t status_would || t status_partial )" warn ;;
      *)       ui_row "$(clean_label "$cat")" "$( [ "$dry" = "1" ] && t status_would || t status_done )" ok ;;
    esac
    i=$((i + 1))
  done
  i=0
  while :; do
    msg=$(pj "$f" "warnings.$i.message"); [ -z "$msg" ] && break
    [ "$i" -lt 3 ] && ui_note "  · ${msg:0:90}"
    i=$((i + 1))
  done
  ui_line
  if [ "$dry" = "1" ]; then
    printf "  ${C_B}%s${C_R} ${C_Y}${C_B}%s${C_R}\n" "$(t preview_total)" "$(ui_size "$moved")"
    ui_note "$(t preview_note)"
  else
    printf "  ${C_B}%s${C_R} ${C_Y}${C_B}%s${C_R}\n" "$(t moved_total)" "$(ui_size "$moved")"
    ui_note "$(t empty_trash_note)"
  fi
  [ -n "$sel" ] && return 0
}
