#!/bin/bash
# MacUp — "Complete check": every check, a total health %, recommendations,
# and an A4 PDF report saved in ~/Downloads.
# shellcheck disable=SC2059,SC2034  # colours in printf formats; H_* results are read by other files

esc() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g'; }

# Recommendations as "level|title|detail|command" lines (level: bad, warn, info, ok).
build_recommendations() {
  REC=""
  local add gb
  add() { REC="${REC}$1|$2|$3|$4"$'\n'; }
  case "$H_SSD_SMART" in *[Ff]ail*) add bad "$(t rec_ssd_fail)" "$(t rec_ssd_fail_d)" "" ;; esac
  if [ "$H_DISK_FREE_PCT" -lt 15 ]; then
    add bad "$(t rec_space_low "$H_DISK_FREE_PCT")" "$(t rec_space_low_d)" "macup clean"
  fi
  gb=$(( ${H_CLEANABLE:-0} / 1000000000 ))
  if [ "${H_CLEANABLE:-0}" -gt 500000000 ]; then
    add warn "$(t rec_cache "$(ui_size "$H_CLEANABLE")")" "$(t rec_cache_d)" "macup clean"
  fi
  if [ "$H_SWAP_MB" -gt 2048 ] || [ "$H_MEM_FREE_PCT" -lt 15 ]; then
    add warn "$(t rec_memory)" "$(t rec_memory_d "$(( H_SWAP_MB / 1024 ))")" ""
  fi
  [ "$H_UPTIME_DAYS" -gt 14 ] && add warn "$(t rec_restart "$H_UPTIME_DAYS")" "$(t rec_restart_d)" ""
  if [ "$H_BAT" = "1" ] && [ -n "$H_BAT_HEALTH" ] && [ "$H_BAT_HEALTH" -lt 80 ]; then
    add bad "$(t rec_battery "$H_BAT_HEALTH")" "$(t rec_battery_d)" ""
  fi
  [ "$H_THERMAL_WARN" = "1" ] && add warn "$(t rec_heat)" "$(t rec_heat_d)" ""
  [ "$P_filevault" = "0" ] && add warn "$(t rec_filevault)" "$(t rec_filevault_d)" ""
  [ "$P_firewall" = "0" ] && add warn "$(t rec_firewall)" "$(t rec_firewall_d)" ""
  [ "$P_gatekeeper" = "0" ] && add bad "$(t rec_gatekeeper)" "$(t rec_gatekeeper_d)" ""
  [ "$P_sip" = "0" ] && add bad "$(t rec_sip)" "$(t rec_sip_d)" ""
  [ "$P_autoupdate" = "0" ] && add warn "$(t rec_updates)" "$(t rec_updates_d)" ""
  [ "$P_xprotect" = "0" ] || [ "$P_responses" = "0" ] && add bad "$(t rec_xprotect)" "$(t rec_xprotect_d)" ""
  [ "$H_STARTUP_BROKEN" -gt 0 ] && add warn "$(t rec_startup "$H_STARTUP_BROKEN")" "$(t rec_startup_d)" ""
  if [ -z "$H_SSD_WEAR" ] && [ "$H_SSD_KIND" = "SSD" ]; then
    add info "$(t rec_ssd_wear)" "$(t rec_ssd_wear_d)" "brew install smartmontools"
  fi
  # "All good" only when there is nothing to fix (info tips don't count).
  if ! printf '%s' "$REC" | grep -qE '^(bad|warn)\|'; then
    add ok "$(t rec_all_good)" "$(t rec_all_good_d)" ""
  fi
  return 0
}

status_word() { # score → ok|warn|bad
  if [ -z "$1" ]; then echo none; elif [ "$1" -ge 80 ]; then echo ok; elif [ "$1" -ge 55 ]; then echo warn; else echo bad; fi
}

# ── Terminal summary ───────────────────────────────────────────────────────

show_scores() {
  ui_score "$(t part_storage)" "$S_STORAGE"
  ui_score "$(t part_ssd)" "$S_SSD"
  ui_score "$(t part_battery)" "$S_BATTERY"
  ui_score "$(t part_memory)" "$S_MEMORY"
  ui_score "$(t part_cpu)" "$S_CPU"
  ui_score "$(t part_protection)" "$S_PROTECTION"
  ui_score "$(t part_cleanup)" "$S_CLEANUP"
}

show_recommendations() {
  local level title detail cmd n=0 mark
  while IFS='|' read -r level title detail cmd; do
    [ -z "$level" ] && continue
    n=$((n + 1))
    case "$level" in bad) mark="${C_Y}✕${C_R}" ;; warn) mark="${C_Y}!${C_R}" ;; ok) mark="${C_B}✓${C_R}" ;; *) mark="${C_D}·${C_R}" ;; esac
    printf "  %b  ${C_B}%s${C_R}\n" "$mark" "$title"
    printf "     ${C_D}%s${C_R}\n" "$detail"
    [ -n "$cmd" ] && printf "     ${C_Y}\$ %s${C_R}\n" "$cmd"
  done <<< "$REC"
}

# ── HTML report (fixed A4 pages) ───────────────────────────────────────────

tile() { # label score note
  local st; st=$(status_word "$2")
  if [ -z "$2" ]; then
    printf '<div class="tile none"><div class="tl">%s</div><div class="tv">—</div><div class="tn">%s</div></div>' "$(esc "$1")" "$(esc "$3")"
  else
    printf '<div class="tile %s"><div class="tl">%s</div><div class="tv">%s<small>%%</small></div><div class="bar"><i style="width:%s%%"></i></div><div class="tn">%s</div></div>' \
      "$st" "$(esc "$1")" "$2" "$2" "$(esc "$3")"
  fi
}

kv() { printf '<tr><th>%s</th><td>%s</td></tr>' "$(esc "$1")" "$(esc "$2")"; }
onoff() { if [ "$2" = "1" ]; then printf '<li class="on"><b>✓</b>%s<span>%s</span></li>' "$(esc "$1")" "$(esc "$(t on)")"; else printf '<li class="off"><b>!</b>%s<span>%s</span></li>' "$(esc "$1")" "$(esc "$(t off)")"; fi; }

build_html() {
  local out="$1" date ring grade cores ssd_wear bat_note
  date=$(date '+%Y-%m-%d %H:%M')
  ring=$(( S_TOTAL * 503 / 100 ))
  grade=$(t "$(grade_key "$S_TOTAL")")
  cores="$H_CORES"
  [ -n "$H_PCORES" ] && [ -n "$H_ECORES" ] && cores=$(t cores_split "$H_CORES" "$H_PCORES" "$H_ECORES")
  if [ -n "$H_SSD_WEAR" ]; then ssd_wear=$(t ssd_wear_value "$(( 100 - H_SSD_WEAR ))"); else ssd_wear=$(t ssd_wear_unknown); fi
  bat_note="$(t bat_cycles "${H_BAT_CYCLES:-—}")"

  {
    cat <<HTML
<!doctype html><html lang="$MACUP_LANG_CODE"><head><meta charset="utf-8"><title>MacUp — $(esc "$(t report_title)")</title>
<style>
*{box-sizing:border-box}html,body{margin:0}
body{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","PingFang SC","Apple SD Gothic Neo",Helvetica,sans-serif;-webkit-font-smoothing:antialiased}
html[lang=ko] body{word-break:keep-all}
.page{width:794px;height:1123px;padding:54px 58px;position:relative;overflow:hidden}
.dark{background:#0a0a0a;color:#fafafa}.light{background:#fff;color:#0a0a0a}
.brand{display:flex;align-items:center;gap:10px;font-weight:800;font-size:18px}
.brand i{width:30px;height:30px;border-radius:8px;background:#1c1c1c;display:grid;place-items:center;color:#ffd905;font-style:normal}
.light .brand i{background:#0a0a0a}
.top{display:flex;justify-content:space-between;align-items:center}
.date{color:#8a8a8a;font-size:13px}
h1{font-size:46px;letter-spacing:-.03em;margin:46px 0 6px;line-height:1.05}
.mac{color:#a3a3a3;font-size:15px}
.hero{display:flex;align-items:center;gap:40px;margin-top:38px}
.ring{position:relative;width:220px;height:220px;flex:none}
.ring b{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;font-weight:800}
.ring b em{font-style:normal;font-size:60px;letter-spacing:-.04em;line-height:1;white-space:nowrap}
.ring b small{font-size:24px;color:#a3a3a3;margin-left:2px}
.ring b span{display:block;font-size:14px;font-weight:600;color:#ffd905;letter-spacing:.08em;text-transform:uppercase;margin-top:8px}
.hero p{color:#cfcfcf;font-size:16px;line-height:1.55;margin:0}
.cache{margin-top:18px;display:inline-block;padding:12px 16px;border-radius:14px;background:#151515;border:1px solid #2a2a2a;font-size:15px}
.cache b{color:#ffd905;font-size:20px}
.tiles{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:40px}
.tile{padding:16px 18px;border-radius:16px;background:#151515;border:1px solid #262626}
.tl{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#a3a3a3}
.tv{font-size:34px;font-weight:800;letter-spacing:-.02em;margin-top:4px}.tv small{font-size:16px;color:#a3a3a3;margin-left:2px}
.bar{height:7px;border-radius:5px;background:#2a2a2a;overflow:hidden;margin:8px 0 8px}.bar i{display:block;height:100%;background:#ffd905;border-radius:5px}
.tile.warn .bar i{background:#e6c300}.tile.bad .bar i{background:#ffd905}.tile.bad{border-color:#ffd905}
.tn{font-size:12.5px;color:#cfcfcf;line-height:1.4}
.foot{position:absolute;left:58px;right:58px;bottom:36px;display:flex;justify-content:space-between;font-size:11.5px;color:#8a8a8a}
h2{font-size:26px;letter-spacing:-.02em;margin:34px 0 14px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.box{border:1px solid #e4e4e7;border-radius:16px;padding:16px 18px;background:#fafafa}
.box h3{margin:0 0 8px;font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#52525b}
table{width:100%;border-collapse:collapse;font-size:13px}th{text-align:left;font-weight:500;color:#52525b;padding:5px 0;width:46%}td{font-weight:650;padding:5px 0}
ul.chk{list-style:none;margin:0;padding:0;display:grid;gap:7px;font-size:13px}
ul.chk li{display:flex;align-items:center;gap:10px}ul.chk b{width:22px;height:22px;border-radius:7px;display:grid;place-items:center;font-size:12px;background:#0a0a0a;color:#ffd905}
ul.chk li.off b{background:#ffd905;color:#0a0a0a}ul.chk span{margin-left:auto;color:#52525b;font-weight:600}
.recs{display:grid;gap:12px;margin-top:6px}
.rec{display:grid;grid-template-columns:36px 1fr;gap:14px;padding:14px 16px;border-radius:16px;border:1px solid #e4e4e7;background:#fafafa}
.rec .n{width:36px;height:36px;border-radius:11px;display:grid;place-items:center;font-weight:800;background:#0a0a0a;color:#ffd905}
.rec.bad .n{background:#ffd905;color:#0a0a0a}.rec.ok .n{background:#ffd905;color:#0a0a0a}
.rec h4{margin:2px 0 4px;font-size:15px}.rec p{margin:0;color:#3f3f46;font-size:13px;line-height:1.5}
.rec code{display:inline-block;margin-top:7px;font:600 12.5px ui-monospace,Menlo,monospace;background:#0a0a0a;color:#ffd905;padding:5px 9px;border-radius:7px}
.good{margin-top:22px;padding:18px 20px;border-radius:18px;background:#0a0a0a;color:#fafafa}
.good h3{margin:0 0 8px;color:#ffd905;font-size:15px}.good p{margin:0 0 6px;font-size:13px;line-height:1.55;color:#d4d4d4}
.light .foot{color:#8a8a8f}
</style></head><body>
<section class="page dark">
  <div class="top"><div class="brand"><i>✦</i>MacUp</div><div class="date">$(esc "$date")</div></div>
  <h1>$(esc "$(t report_title)")</h1>
  <div class="mac">$(esc "$H_MODEL") · $(esc "$H_CHIP") · macOS $(esc "$H_MACOS")</div>
  <div class="hero">
    <div class="ring"><svg width="220" height="220" viewBox="0 0 200 200"><circle cx="100" cy="100" r="80" fill="none" stroke="#262626" stroke-width="16"/><circle cx="100" cy="100" r="80" fill="none" stroke="#ffd905" stroke-width="16" stroke-linecap="round" stroke-dasharray="$ring 503" transform="rotate(-90 100 100)"/></svg>
      <b><em>${S_TOTAL}<small>%</small></em><span>$(esc "$grade")</span></b></div>
    <div><p>$(esc "$(t report_intro)")</p>
      <div class="cache">$(esc "$(t report_cache)") <b>$(esc "$(ui_size "${H_CLEANABLE:-0}")")</b></div></div>
  </div>
  <div class="tiles">
HTML
    tile "$(t part_storage)" "$S_STORAGE" "$(t note_storage "$(ui_size "$H_DISK_FREE")" "$H_DISK_FREE_PCT")"
    tile "$(t part_ssd)" "$S_SSD" "$H_SSD_KIND · SMART: ${H_SSD_SMART:-—}"
    if [ "$H_BAT" = "1" ]; then tile "$(t part_battery)" "$S_BATTERY" "$(t note_battery "${H_BAT_HEALTH:-—}" "${H_BAT_CYCLES:-—}")"
    else tile "$(t part_battery)" "" "$(t no_battery)"; fi
    tile "$(t part_memory)" "$S_MEMORY" "$(t note_memory "$H_MEM_FREE_PCT" "$(( H_SWAP_MB / 1024 ))")"
    tile "$(t part_cpu)" "$S_CPU" "$(t note_cpu "$H_CPU_LOAD_PCT" "$H_UPTIME_DAYS")"
    tile "$(t part_protection)" "$S_PROTECTION" "$(t note_protection "$P_PASSED" "$P_TOTAL")"
    cat <<HTML
  </div>
  <div class="foot"><span>$(esc "$(t report_footer)")</span><span>1 / 3</span></div>
</section>

<section class="page light">
  <div class="top"><div class="brand"><i>✦</i>MacUp</div><div class="date">$(esc "$date")</div></div>
  <h2>$(esc "$(t report_details)")</h2>
  <div class="grid2">
    <div class="box"><h3>$(esc "$(t part_storage)")</h3><table>
HTML
    kv "$(t k_total)" "$(ui_size "$H_DISK_TOTAL")"
    kv "$(t k_used)" "$(ui_size "$H_DISK_USED")"
    kv "$(t k_free)" "$(ui_size "$H_DISK_FREE") ($H_DISK_FREE_PCT%)"
    kv "$(t k_hidden_cache)" "$(ui_size "${H_CLEANABLE:-0}")"
    printf '</table></div><div class="box"><h3>%s</h3><table>' "$(esc "$(t part_ssd)")"
    kv "$(t k_model)" "${H_SSD_MODEL:-—}"
    kv "$(t k_type)" "$H_SSD_KIND"
    kv "S.M.A.R.T." "${H_SSD_SMART:-—}"
    kv "$(t k_ssd_health)" "$ssd_wear"
    printf '</table></div><div class="box"><h3>%s</h3><table>' "$(esc "$(t part_battery)")"
    if [ "$H_BAT" = "1" ]; then
      kv "$(t k_bat_health)" "${H_BAT_HEALTH:-—}%"
      kv "$(t k_cycles)" "$bat_note"
      kv "$(t k_condition)" "${H_BAT_CONDITION:-—}"
      kv "$(t k_charge)" "${H_BAT_CHARGE:-—}%"
    else kv "$(t part_battery)" "$(t no_battery)"; fi
    printf '</table></div><div class="box"><h3>%s</h3><table>' "$(esc "$(t part_memory)")"
    kv "$(t k_ram)" "$H_MEM_LABEL"
    kv "$(t k_mem_free)" "$H_MEM_FREE_PCT%"
    kv "$(t k_swap)" "$(awk -v m="$H_SWAP_MB" 'BEGIN { printf "%.1f GB", m / 1024 }')"
    printf '</table></div><div class="box"><h3>%s</h3><table>' "$(esc "$(t part_cpu)")"
    kv "$(t k_chip)" "$H_CHIP"
    kv "$(t k_cores)" "$cores"
    kv "$(t k_load)" "$H_CPU_LOAD_PCT%"
    kv "$(t k_heat)" "$( [ "$H_THERMAL_WARN" = "1" ] && t heat_warn || t heat_ok )"
    kv "$(t k_uptime)" "$(t days "$H_UPTIME_DAYS")"
    printf '</table></div><div class="box"><h3>%s</h3><table>' "$(esc "$(t part_gpu)")"
    kv "$(t k_gpu)" "${H_GPU:-—}"
    kv "$(t k_gpu_cores)" "${H_GPU_CORES:-—}"
    kv "Metal" "${H_GPU_METAL:-—}"
    kv "$(t k_displays)" "${H_DISPLAYS:-—}"
    printf '</table></div></div><h2>%s</h2><div class="grid2"><div class="box"><ul class="chk">' "$(esc "$(t part_protection)")"
    onoff "Gatekeeper" "$P_gatekeeper"
    onoff "$(t p_sip)" "$P_sip"
    onoff "FileVault" "$P_filevault"
    onoff "$(t p_firewall)" "$P_firewall"
    onoff "XProtect${H_XPROTECT_VERSION:+ $H_XPROTECT_VERSION}" "$P_xprotect"
    onoff "$(t p_responses)" "$P_responses"
    onoff "$(t p_autoupdate)" "$P_autoupdate"
    printf '</ul></div><div class="box"><h3>%s</h3><table>' "$(esc "$(t part_performance)")"
    kv "$(t k_startup)" "$H_STARTUP"
    kv "$(t k_startup_broken)" "$H_STARTUP_BROKEN"
    printf '%s\n' "$H_TOP_CPU" | head -3 | while IFS=$'\t' read -r name pct; do
      [ -n "$name" ] && kv "CPU · $name" "$pct%"
    done
    cat <<HTML
    </table></div></div>
  <div class="foot"><span>$(esc "$(t report_footer)")</span><span>2 / 3</span></div>
</section>

<section class="page light">
  <div class="top"><div class="brand"><i>✦</i>MacUp</div><div class="date">$(esc "$date")</div></div>
  <h2>$(esc "$(t report_recs)")</h2>
  <div class="recs">
HTML
    local n=0 level title detail cmd
    while IFS='|' read -r level title detail cmd; do
      [ -z "$level" ] && continue
      n=$((n + 1)); [ "$n" -gt 7 ] && break
      printf '<div class="rec %s"><div class="n">%s</div><div><h4>%s</h4><p>%s</p>%s</div></div>\n' \
        "$level" "$n" "$(esc "$title")" "$(esc "$detail")" "$( [ -n "$cmd" ] && printf '<code>$ %s</code>' "$(esc "$cmd")")"
    done <<< "$REC"
    cat <<HTML
  </div>
  <div class="good"><h3>$(esc "$(t good_title)")</h3>
    <p>$(esc "$(t good_1)")</p><p>$(esc "$(t good_2)")</p><p>$(esc "$(t good_3)")</p></div>
  <div class="foot"><span>$(esc "$(t report_footer)")</span><span>3 / 3</span></div>
</section>
</body></html>
HTML
  } > "$out"
}

# PDF into ~/Downloads (HTML next to it if the PDF renderer cannot run).
save_report() {
  local stamp dir html pdf
  stamp=$(date '+%Y-%m-%d-%H%M')
  dir="$HOME/Downloads"; [ -d "$dir" ] || dir="$HOME"
  html="$MACUP_TMP/report.html"
  pdf="$dir/MacUp-Health-Report-$stamp.pdf"
  build_html "$html"
  if "$MACUP_ROOT/bin/macup-pdf" "$html" "$pdf" >/dev/null 2>&1 && [ -s "$pdf" ]; then
    REPORT_FILE="$pdf"
  else
    REPORT_FILE="$dir/MacUp-Health-Report-$stamp.html"
    cp "$html" "$REPORT_FILE"
  fi
}

cmd_check() {
  macup_tmp
  ui_title "$(t check_title)" "5"
  ui_note "$(t check_intro)"
  echo
  ui_spin "$(t checking)" collect_all_quiet
  load_collected
  echo
  printf "  ${C_B}%s${C_R}  ${C_Y}${C_B}%s%%${C_R}  ${C_D}%s${C_R}\n" "$(t mac_health)" "$S_TOTAL" "$(t "$(grade_key "$S_TOTAL")")"
  printf "  %s\n" "$(ui_bar "$S_TOTAL" 50)"
  echo
  show_scores
  ui_title "$(t report_recs)" "→"
  build_recommendations
  show_recommendations
  echo
  ui_spin "$(t making_pdf)" save_report_quiet
  REPORT_FILE=$(cat "$MACUP_TMP/report.path" 2>/dev/null)
  ui_line
  case "$REPORT_FILE" in
    *.pdf) printf "  ${C_B}✓${C_R} %s\n     ${C_Y}%s${C_R}\n" "$(t pdf_saved)" "$REPORT_FILE" ;;
    *) printf "  ${C_Y}!${C_R} %s\n     ${C_Y}%s${C_R}\n" "$(t html_saved)" "$REPORT_FILE" ;;
  esac
  if [ -t 0 ] && [ -n "$REPORT_FILE" ] && ui_yes "$(t open_report_q)" y; then open "$REPORT_FILE"; fi
  if [ -t 0 ] && [ "${H_CLEANABLE:-0}" -gt 500000000 ] && ui_yes "$(t clean_now_q "$(ui_size "$H_CLEANABLE")")" n; then cmd_clean; fi
  return 0
}

# Spinner runs in a subshell, so results travel through a file.
collect_all_quiet() {
  collect_all
  local v
  for v in $(compgen -v | grep -E '^(H_|P_|S_[A-Z])'); do
    printf '%s=%q\n' "$v" "${!v}"
  done > "$MACUP_TMP/collected.sh"
}
load_collected() { [ -f "$MACUP_TMP/collected.sh" ] && . "$MACUP_TMP/collected.sh"; }
save_report_quiet() { build_recommendations; save_report; printf '%s' "$REPORT_FILE" > "$MACUP_TMP/report.path"; }
