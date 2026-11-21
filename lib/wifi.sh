#!/bin/bash
# MacUp — 7 · Wi-Fi Check: is the Wi-Fi OK — and if not, what fixes it.
# Copyright (c) 2026 cdav.io · GPL-3.0 · https://github.com/CDAVIO/MacUp-Cleaner-CDAV.IO
#
# The check only reads. It uses tools that ship with macOS:
#   system_profiler  band, channel, signal and the networks nearby
#   ping             your router and 1.1.1.1 (ping jumps = a Wi-Fi problem)
#   nettop           which apps use the network right now (5 seconds)
#   networkQuality   Apple's built-in speed test (talks to Apple's test servers)
# The fix never changes a setting by itself: MacUp writes down the current
# values first, opens the right System Settings page (or your router's page)
# and checks again afterwards. No admin password. Bash 3.2 compatible.
# shellcheck disable=SC2059,SC2034  # colours in printf formats; W_* results are read by other functions

WIFI_DIR="$HOME/Library/Application Support/MacUp"
WIFI_BEFORE="$WIFI_DIR/wifi-before.txt"
WIFI_LAST="$WIFI_DIR/wifi-last.txt"
WIFI_PANE_AIRDROP="x-apple.systempreferences:com.apple.AirDrop-Handoff-Settings.extension"
WIFI_PANE_BATTERY="x-apple.systempreferences:com.apple.Battery-Settings.extension"
WIFI_PING_COUNT="${WIFI_PING_COUNT:-20}"
WIFI_APPS_SECONDS="${WIFI_APPS_SECONDS:-5}"

wifi_reset() {
  W_DEV=""; W_IP=""; W_ROUTER=""; W_NAME=""; W_PHY=""; W_GEN=""; W_RATE=""
  W_CH=""; W_BAND=""; W_WIDTH=""; W_SIGNAL=""; W_NOISE=""; W_COUNTRY=""
  W_SAME=0; W_SHARE=0; W_BEST=""; W_BEST_N=0; W_NEARBY=0; W_CHANNELS=""
  W_R_MED=""; W_R_MAX=""; W_R_JIT=""; W_R_SPIKES=0; W_R_LOSS=0
  W_I_MED=""; W_I_MAX=""; W_I_JIT=""; W_I_SPIKES=0; W_I_LOSS=0
  W_DL=""; W_UL=""
  W_DNS=""; W_VPN=""; W_PROXY=0; W_LOWPOWER=0; W_AWDL=0
  W_AIRDROP=""; W_HANDOFF=""; W_AIRPLAY=""
  W_APPS=""; W_APPS_TOTAL="0"
  W_PLAN="${W_PLAN:-}"
}

# ── Wi-Fi details ───────────────────────────────────────────────────────────

wifi_device() {
  networksetup -listallhardwareports 2>/dev/null |
    awk '/^Hardware Port: (Wi-Fi|AirPort)$/ { getline; sub(/^Device: */, ""); print; exit }'
}

# The joined network and the networks nearby, one per line:
#   CUR|<channel>|<signal / noise>|<phy>|<rate>|<security>|<name>|<country>
#   OTH|<channel>|<signal / noise>|<phy>||<security>|<name>|
# Channel looks like "36 (5GHz, 80MHz)". The JSON keys are the same in every
# language; the text fallback below only looks at the shape of the values.
wifi_nets_from_json() { # FILE DEVICE
  local f="$1" dev="$2" i name base cur others
  for ((i = 0; i < 8; i++)); do
    name=$(pj "$f" "SPAirPortDataType.0.spairport_airport_interfaces.$i._name")
    [ -z "$name" ] && return 1
    [ "$name" = "$dev" ] && break
  done
  [ "$name" = "$dev" ] || return 1
  base="SPAirPortDataType.0.spairport_airport_interfaces.$i"
  cur=$(plutil -extract "$base.spairport_current_network_information" json -o - "$f" 2>/dev/null) || cur=""
  others=$(plutil -extract "$base.spairport_airport_other_local_wireless_networks" json -o - "$f" 2>/dev/null) || others=""
  case "$cur$others" in *spairport_network_channel*) ;; *) return 1 ;; esac
  printf '%s\n%s\n' "$cur" "$others" | awk '
    function jget(o, k,   i, r) {
      i = index(o, "\"" k "\""); if (!i) return ""
      r = substr(o, i + length(k) + 2); sub(/^[ :]*/, "", r)
      if (substr(r, 1, 1) == "\"") { r = substr(r, 2); sub(/".*/, "", r) }
      else sub(/[,}\]].*/, "", r)
      gsub(/\\\//, "/", r); gsub(/\|/, " ", r)
      return r
    }
    function out(kind, o) {
      if (jget(o, "spairport_network_channel") == "") return
      printf "%s|%s|%s|%s|%s|%s|%s|%s\n", kind, jget(o, "spairport_network_channel"), jget(o, "spairport_signal_noise"),
        jget(o, "spairport_network_phymode"), (kind == "CUR" ? jget(o, "spairport_network_rate") : ""),
        jget(o, "spairport_security_mode"), jget(o, "_name"), (kind == "CUR" ? jget(o, "spairport_network_country_code") : "")
    }
    NR == 1 { out("CUR", $0); next }
    {
      n = split($0, part, /\},[ ]*\{/)
      for (j = 1; j <= n; j++) out("OTH", part[j])
    }'
}

wifi_nets_from_text() { # DEVICE  (reads system_profiler text on stdin)
  awk -v dev="$1" '
    function ind(s) { match(s, /^ */); return RLENGTH }
    ind($0) == 8 && /^ *[A-Za-z0-9]+:$/ { iface = $0; gsub(/[ :]/, "", iface); next }
    iface != dev { next }
    { d = ind($0) }
    d == 10 && /:$/ { sec++; next }
    d == 12 && /:$/ { n++; v = $0; sub(/^ */, "", v); sub(/:$/, "", v); name[n] = v; s[n] = sec; next }
    d >= 14 && n > 0 {
      v = $0; sub(/^ *[^:]*: */, "", v)
      if (v ~ /^[0-9]+ \([0-9.]+ ?GHz(, [0-9]+ ?MHz)?\)$/) ch[n] = v
      else if (v ~ /^-?[0-9]+ dBm \/ -?[0-9]+ dBm$/) sn[n] = v
      else if (v ~ /^802\.11/) phy[n] = v
      else if (v ~ /^[0-9]+$/) { if (rate[n] == "") rate[n] = v; nums[n]++ }
      else if (v ~ /^[A-Z][A-Z]$/) cc[n] = v
      else if (v ~ /WPA|WEP|Personal|Enterprise|Open|None/) secu[n] = v
    }
    END {
      # The joined network is the only one with a transmit rate and MCS index.
      cur = 0
      for (i = 1; i <= n; i++) if (nums[i] > 0 && ch[i] != "") { cur = i; break }
      for (i = 1; i <= n; i++) {
        if (ch[i] == "") continue
        printf "%s|%s|%s|%s|%s|%s|%s|%s\n", (i == cur ? "CUR" : "OTH"), ch[i], sn[i], phy[i], (i == cur ? rate[i] : ""), secu[i], name[i], (i == cur ? cc[i] : "")
      }
    }'
}

# wifi_analyze COUNTRY < nets → one line:
#   ch band width signal noise gen same share best best_n nearby
# and, on the following lines, "CH <band> <channel> <count>" for the summary.
# "share" counts nearby networks whose channel overlaps yours (an 80 MHz
# channel covers four 20 MHz ones); "best" is the emptiest choice for the same
# width. Your own router's second network is not counted when it can be told.
wifi_analyze() {
  awk -F'|' -v country="${1:-}" '
    function chparse(s, a,   b, w) {
      a["ch"] = s + 0; b = ""; w = 20
      if (match(s, /[0-9.]+ ?GHz/)) { b = substr(s, RSTART, RLENGTH); gsub(/[^0-9.]/, "", b) }
      if (match(s, /[0-9]+ ?MHz/)) { w = substr(s, RSTART, RLENGTH); gsub(/[^0-9]/, "", w); w += 0 }
      if (b == "2" || b == "2.4") b = "2.4"
      if (b == "") b = (a["ch"] <= 14) ? "2.4" : "5"
      a["band"] = b; a["width"] = w
    }
    function top(p,   n, x) { gsub(/802\.11/, "", p); n = split(p, x, "/"); return x[n] }
    # range in 20 MHz slots → LO, HI (globals)
    function span(band, ch, w,   idx, k, start) {
      k = int(w / 20); if (k < 1) k = 1
      if (band == "2.4") { LO = ch - 2; HI = ch + 2 + (w >= 40 ? 4 : 0); return }
      if (band == "6") { idx = int((ch - 1) / 4); start = int(idx / k) * k; LO = start; HI = start + k - 1; return }
      if (ch >= 149) { idx = int((ch - 149) / 4); start = 29 + int(idx / k) * k }
      else { idx = int((ch - 36) / 4); start = int(idx / k) * k }
      LO = start; HI = start + k - 1
    }
    function overlap(band, c1, w1, c2, w2,   a, b) {
      span(band, c1, w1); a = LO; b = HI
      span(band, c2, w2)
      return !(HI < a || LO > b)
    }
    $1 == "CUR" { cur_ch = $2; cur_sn = $3; cur_phy = $4; cur_sec = $6; cur_name = $7; next }
    $1 == "OTH" { n++; o_ch[n] = $2; o_sn[n] = $3; o_phy[n] = $4; o_sec[n] = $6; o_name[n] = $7 }
    END {
      if (cur_ch == "") { print "- - - - - - 0 0 - 0 " n; exit }
      chparse(cur_ch, c); ch = c["ch"]; band = c["band"]; w = c["width"]
      split(cur_sn, sn, /[^-0-9]+/); sig = ""; noi = ""
      for (i = 1; i in sn; i++) if (sn[i] ~ /^-?[0-9]+$/) { if (sig == "") sig = sn[i]; else if (noi == "") noi = sn[i] }
      p = cur_phy; gen = "-"
      if (p ~ /be/) gen = "7"; else if (p ~ /ax/) gen = (band == "6" ? "6E" : "6"); else if (p ~ /ac/) gen = "5"; else if (p ~ /n/) gen = "4"
      named = (cur_name != "" && cur_name !~ /redacted/)
      own = 0
      for (i = 1; i <= n; i++) {
        skip[i] = 0
        if (named && o_name[i] == cur_name) { skip[i] = 1; continue }
        if (!named && !own && o_ch[i] == cur_ch && o_sec[i] == cur_sec && top(o_phy[i]) == top(cur_phy)) { skip[i] = 1; own = 1 }
      }
      same = 0; share = 0; nearby = 0
      for (i = 1; i <= n; i++) {
        if (skip[i]) continue
        nearby++
        chparse(o_ch[i], o)
        cnt[o["band"] SUBSEP o["ch"]]++
        if (o["band"] != band) continue
        if (o["ch"] == ch) same++
        if (overlap(band, ch, w, o["ch"], o["width"])) share++
        ob[i] = o["band"]; oc[i] = o["ch"]; ow[i] = o["width"]
      }
      best = ch; bestn = share
      if (band == "5") {
        eu = " AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE GB NO CH IS LI "
        if (w >= 160) list = "36 100 149"; else list = "36 149 52 100 132 116"
        if (index(eu, " " toupper(country) " ")) gsub(/ ?149/, "", list)
      } else if (band == "2.4") list = "1 6 11"
      else list = ""
      m = split(list, cand, " ")
      first = 1
      for (k = 1; k <= m; k++) {
        cc = cand[k] + 0; cn = 0
        for (i = 1; i <= n; i++) if (!skip[i] && ob[i] == band && overlap(band, cc, w, oc[i], ow[i])) cn++
        if (first || cn < bestn2) { best2 = cc; bestn2 = cn; first = 0 }
      }
      if (m > 0 && bestn2 < share) { best = best2; bestn = bestn2 }
      printf "%s %s %s %s %s %s %d %d %s %d %d\n", ch, band, w, (sig == "" ? "-" : sig), (noi == "" ? "-" : noi), gen, same, share, best, bestn, nearby
      for (key in cnt) { split(key, kk, SUBSEP); printf "CH %s %s %d\n", kk[1], kk[2], cnt[key] }
    }'
}

wifi_scan() {
  local f="$MACUP_TMP/wifi.json" nets="$MACUP_TMP/wifi.nets" line
  system_profiler -json SPAirPortDataType > "$f" 2>/dev/null || true
  if ! wifi_nets_from_json "$f" "$W_DEV" > "$nets" 2>/dev/null || [ ! -s "$nets" ]; then
    system_profiler SPAirPortDataType 2>/dev/null | wifi_nets_from_text "$W_DEV" > "$nets" || true
  fi
  W_NAME=$(awk -F'|' '$1 == "CUR" { print $7; exit }' "$nets")
  W_PHY=$(awk -F'|' '$1 == "CUR" { print $4; exit }' "$nets")
  W_RATE=$(awk -F'|' '$1 == "CUR" { print $5; exit }' "$nets")
  W_COUNTRY=$(awk -F'|' '$1 == "CUR" { print $8; exit }' "$nets")
  wifi_analyze "$W_COUNTRY" < "$nets" > "$MACUP_TMP/wifi.analysis"
  read -r W_CH W_BAND W_WIDTH W_SIGNAL W_NOISE W_GEN W_SAME W_SHARE W_BEST W_BEST_N W_NEARBY < "$MACUP_TMP/wifi.analysis"
  W_CHANNELS=$(awk -v b="$W_BAND" '$1 == "CH" && $2 == b { printf "%s %s\n", $3, $4 }' "$MACUP_TMP/wifi.analysis" | sort -n | awk '{ printf "%s%s (%s)", (NR > 1 ? " · " : ""), $1, $2 }')
  for line in W_CH W_BAND W_WIDTH W_SIGNAL W_NOISE W_GEN W_BEST; do
    [ "${!line:-}" = "-" ] && printf -v "$line" '%s' ""
  done
  return 0
}

# ── ping, speed, apps ───────────────────────────────────────────────────────

# ping output on stdin → "median worst jitter jumps loss%" (ms, rounded)
# A jump is a reply 3× slower than usual (and at least 15 ms slower).
wifi_ping_parse() {
  awk '
    /time=/ { v = $0; sub(/.*time=/, "", v); sub(/[^0-9.].*/, "", v); ms[++n] = v + 0 }
    / packets transmitted/ { sent = $1 + 0 }
    END {
      if (n == 0) { print "- - - 0 100"; exit }
      for (i = 1; i <= n; i++) s[i] = ms[i]
      for (i = 2; i <= n; i++) { k = s[i]; j = i - 1; while (j > 0 && s[j] > k) { s[j + 1] = s[j]; j-- } s[j + 1] = k }
      med = (n % 2) ? s[(n + 1) / 2] : (s[n / 2] + s[n / 2 + 1]) / 2
      sum = 0; for (i = 2; i <= n; i++) { d = ms[i] - ms[i - 1]; sum += (d < 0 ? -d : d) }
      lim = med * 3; if (lim < med + 15) lim = med + 15
      jumps = 0; for (i = 1; i <= n; i++) if (ms[i] > lim) jumps++
      loss = (sent > n) ? int((sent - n) * 100 / sent + 0.5) : 0
      printf "%.0f %.0f %.0f %d %d\n", med, s[n], (n > 1 ? sum / (n - 1) : 0), jumps, loss
    }'
}

wifi_ping() { # HOST → stats line
  ping -c "$WIFI_PING_COUNT" -i 0.2 -t 15 "$1" 2>/dev/null | wifi_ping_parse
}

# networkQuality -c JSON → "download upload" in Mbps ("" when it failed)
wifi_speed_parse() { # FILE
  local dl ul
  dl=$(pj "$1" dl_throughput); ul=$(pj "$1" ul_throughput)
  awk -v d="${dl:-0}" -v u="${ul:-0}" 'BEGIN {
    printf "%s %s\n", (d > 0 ? sprintf("%.0f", d / 1e6) : "-"), (u > 0 ? sprintf("%.0f", u / 1e6) : "-") }'
}

wifi_speed() {
  local f="$MACUP_TMP/nq.json"
  W_DL=""; W_UL=""
  command -v networkQuality >/dev/null 2>&1 || return 0
  # -s: download, then upload (at the same time Wi-Fi would share its airtime).
  networkQuality -s -c -I "$W_DEV" > "$f" 2>/dev/null || networkQuality -s -c > "$f" 2>/dev/null || return 0
  read -r W_DL W_UL <<< "$(wifi_speed_parse "$f")"
  [ "$W_DL" = "-" ] && W_DL=""
  [ "$W_UL" = "-" ] && W_UL=""
  return 0
}

# Two nettop samples SECONDS apart → "Mbps<TAB>app" lines, busiest first.
wifi_apps_parse() { # FIRST SECOND SECONDS
  awk -F, -v secs="${3:-5}" '
    NR == FNR { if (FNR > 1 && $1 != "") { i[$1] = $2; o[$1] = $3 } next }
    FNR > 1 && ($1 in i) {
      d = ($2 - i[$1]) + ($3 - o[$1])
      if (d <= 0) next
      name = $1; sub(/\.[0-9]+$/, "", name); sub(/ +$/, "", name)
      mb[name] += d * 8 / secs / 1e6
    }
    END { for (k in mb) printf "%.2f\t%s\n", mb[k], k }' "$1" "$2" | sort -rn
}

wifi_apps() {
  local a="$MACUP_TMP/nettop.1" b="$MACUP_TMP/nettop.2"
  W_APPS=""; W_APPS_TOTAL="0"
  command -v nettop >/dev/null 2>&1 || return 0
  nettop -P -L 1 -x -J bytes_in,bytes_out > "$a" 2>/dev/null || return 0
  sleep "$WIFI_APPS_SECONDS"
  nettop -P -L 1 -x -J bytes_in,bytes_out > "$b" 2>/dev/null || return 0
  wifi_apps_parse "$a" "$b" "$WIFI_APPS_SECONDS" > "$MACUP_TMP/wifi.apps"
  W_APPS=$(head -3 "$MACUP_TMP/wifi.apps" | awk -F'\t' '$1 >= 0.05 { printf "%s%s %.1f Mbps", (n++ ? " · " : ""), $2, $1 }')
  W_APPS_TOTAL=$(awk -F'\t' '{ s += $1 } END { printf "%.1f", s }' "$MACUP_TMP/wifi.apps")
}

# ── this Mac ────────────────────────────────────────────────────────────────

# AirDrop, Handoff and AirPlay Receiver keep a second, hidden Wi-Fi link
# (AWDL) busy. That link makes the Wi-Fi radio hop away for a moment about
# once a second — the ping jumps you see even to your own router.
wifi_read_continuity() {
  local v
  v=$(defaults read com.apple.sharingd DiscoverableMode 2>/dev/null) || v=""
  case "$v" in
    Off) W_AIRDROP="off" ;;
    Everyone*) W_AIRDROP="everyone" ;;
    Contacts*) W_AIRDROP="contacts" ;;
    *) W_AIRDROP="" ;;
  esac
  v=$(defaults -currentHost read com.apple.coreservices.useractivityd ActivityAdvertisingAllowed 2>/dev/null) || v=""
  case "$v" in 0) W_HANDOFF="off" ;; 1) W_HANDOFF="on" ;; *) W_HANDOFF="" ;; esac
  v=$(defaults -currentHost read com.apple.controlcenter AirplayRecieverEnabled 2>/dev/null) || v=""
  case "$v" in 0) W_AIRPLAY="off" ;; 1) W_AIRPLAY="on" ;; *) W_AIRPLAY="" ;; esac
  W_AWDL=0
  ifconfig awdl0 2>/dev/null | grep -q 'status: active' && W_AWDL=1
  return 0
}

wifi_mac_settings() {
  W_DNS=$(scutil --dns 2>/dev/null | awk '
    /^resolver #1$/ { r = 1; next } /^resolver #/ { if (r) exit }
    r && /nameserver\[/ { printf "%s%s", (n++ ? ", " : ""), $3 }')
  W_VPN=$(scutil --nc list 2>/dev/null | awk -F'"' '/\(Connected\)/ { printf "%s%s", (n++ ? ", " : ""), $2 }')
  W_PROXY=$(scutil --proxy 2>/dev/null | awk '/(HTTPEnable|HTTPSEnable|SOCKSEnable|ProxyAutoConfigEnable) : 1/ { p = 1 } END { print p + 0 }')
  W_LOWPOWER=$(pmset -g 2>/dev/null | awk '$1 == "lowpowermode" { lp = $2 } $1 == "powermode" { pm = $2 } END { print ((lp == "1" || (lp == "" && pm == "1")) ? 1 : 0) }')
  wifi_read_continuity
}

# ── collect (runs under the spinner, results travel through a file) ─────────

wifi_collect() {
  progress wifi_step_scan;  wifi_scan
  progress wifi_step_ping
  [ -n "$W_ROUTER" ] && read -r W_R_MED W_R_MAX W_R_JIT W_R_SPIKES W_R_LOSS <<< "$(wifi_ping "$W_ROUTER")"
  read -r W_I_MED W_I_MAX W_I_JIT W_I_SPIKES W_I_LOSS <<< "$(wifi_ping 1.1.1.1)"
  progress wifi_step_mac;   wifi_mac_settings
  progress wifi_step_apps;  wifi_apps
  progress wifi_step_speed; wifi_speed
  wifi_save_state
}

wifi_measure() { # ping + speed only (for the after test)
  progress wifi_step_ping
  [ -n "$W_ROUTER" ] && read -r W_R_MED W_R_MAX W_R_JIT W_R_SPIKES W_R_LOSS <<< "$(wifi_ping "$W_ROUTER")"
  read -r W_I_MED W_I_MAX W_I_JIT W_I_SPIKES W_I_LOSS <<< "$(wifi_ping 1.1.1.1)"
  progress wifi_step_scan;  wifi_scan
  progress wifi_step_mac;   wifi_read_continuity
  progress wifi_step_speed; wifi_speed
  wifi_save_state
}

wifi_save_state() {
  local v
  for v in $(compgen -v | grep -E '^W_'); do printf '%s=%q\n' "$v" "${!v}"; done > "$MACUP_TMP/wifi.state"
}

wifi_load_state() {
  local v
  for v in R_MED R_MAX R_JIT R_SPIKES R_LOSS I_MED I_MAX I_JIT I_SPIKES I_LOSS; do
    printf -v "W_$v" '%s' ""
  done
  # shellcheck disable=SC1091
  [ -f "$MACUP_TMP/wifi.state" ] && . "$MACUP_TMP/wifi.state"
  for v in W_R_MED W_R_MAX W_R_JIT W_I_MED W_I_MAX W_I_JIT; do
    [ "${!v:-}" = "-" ] && printf -v "$v" '%s' ""
  done
  return 0
}

# ── what to do ──────────────────────────────────────────────────────────────

wifi_continuity_busy() {
  [ "$W_AIRDROP" = "everyone" ] || [ "$W_AIRDROP" = "contacts" ] || [ "$W_HANDOFF" = "on" ] || [ "$W_AIRPLAY" = "on" ]
}

wifi_has_jumps() {
  [ "${W_R_SPIKES:-0}" -ge 2 ] || [ "${W_R_JIT:-0}" -ge 10 ] 2>/dev/null
}

wifi_channel_fix() {
  [ -n "$W_BEST" ] && [ "$W_BEST" != "$W_CH" ] && [ "${W_SHARE:-0}" -ge 2 ] && [ "${W_BEST_N:-0}" -lt "${W_SHARE:-0}" ]
}

wifi_is_dfs() { [ "${1:-0}" -ge 52 ] 2>/dev/null && [ "${1:-0}" -le 144 ]; }

wifi_pct() { awk -v a="${1:-0}" -v b="${2:-0}" 'BEGIN { if (b > 0) printf "%.0f", a * 100 / b }'; }

# REC lines: level|title|detail|command (same format as the complete check)
wifi_recommendations() {
  REC=""
  add() { REC="${REC}$1|$2|$3|${4:-}"$'\n'; }
  if [ -n "$W_SIGNAL" ] && [ "$W_SIGNAL" -lt -70 ] 2>/dev/null; then
    add bad "$(t wifi_rec_signal "$W_SIGNAL")" "$(t wifi_rec_signal_d)"
  fi
  if [ "$W_BAND" = "2.4" ]; then
    add warn "$(t wifi_rec_band)" "$(t wifi_rec_band_d)"
  fi
  if wifi_continuity_busy && { wifi_has_jumps || [ "$W_AWDL" = "1" ]; }; then
    add warn "$(t wifi_rec_awdl)" "$(t wifi_rec_awdl_d)"
  fi
  if wifi_channel_fix; then
    local extra=""
    wifi_is_dfs "$W_BEST" && extra=" $(t wifi_rec_dfs)"
    add warn "$(t wifi_rec_channel "$W_BEST" "$W_WIDTH")" "$(t wifi_rec_channel_d "$W_SHARE" "$W_CH" "$W_BEST_N")$extra"
  fi
  if [ -n "$W_VPN" ]; then add warn "$(t wifi_rec_vpn "$W_VPN")" "$(t wifi_rec_vpn_d)"; fi
  if [ "$W_LOWPOWER" = "1" ]; then add warn "$(t wifi_rec_lowpower)" "$(t wifi_rec_lowpower_d)"; fi
  local busy_mb busy_app
  busy_mb=$(head -1 "$MACUP_TMP/wifi.apps" 2>/dev/null | cut -f1)
  busy_app=$(head -1 "$MACUP_TMP/wifi.apps" 2>/dev/null | cut -f2)
  if [ -n "$busy_mb" ] && awk -v m="$busy_mb" 'BEGIN { exit !(m >= 5) }'; then
    add warn "$(t wifi_rec_app "$busy_app" "$(awk -v m="$busy_mb" 'BEGIN { printf "%.0f", m }')")" "$(t wifi_rec_app_d)"
  fi
  case "$W_GEN" in
    4|5)
      local pct=""
      [ -n "$W_PLAN" ] && [ -n "$W_DL" ] && pct=$(wifi_pct "$W_DL" "$W_PLAN")
      if [ -z "$pct" ] || [ "$pct" -lt 60 ]; then
        add info "$(t wifi_rec_router "$W_GEN")" "$(t wifi_rec_router_d)"
      fi
      ;;
  esac
  if [ -z "$REC" ]; then add ok "$(t wifi_rec_all_good)" "$(t wifi_rec_all_good_d)"; fi
  unset -f add
  return 0
}

# ── screens ─────────────────────────────────────────────────────────────────

wifi_word() { # on/off/everyone/contacts/"" → translated word
  case "$1" in
    on) t on ;; off) t off ;;
    everyone) t wifi_airdrop_everyone ;; contacts) t wifi_airdrop_contacts ;;
    *) t wifi_unknown ;;
  esac
}

# wifi_mark VALUE BAD… → ok, warn (VALUE is one of BAD) or info (macOS did not say)
wifi_mark() {
  local v="$1" b; shift
  [ -z "$v" ] && { echo info; return; }
  for b; do [ "$v" = "$b" ] && { echo warn; return; }; done
  echo ok
}

wifi_airdrop_word() { if [ "$1" = "off" ]; then t wifi_airdrop_off; else wifi_word "$1"; fi; }

wifi_show_speed() {
  printf "  ${C_D}%s${C_R}\n" "$(t part_wifi_speed)"
  if [ -n "$W_DL" ]; then
    if [ -n "$W_PLAN" ]; then
      local pct; pct=$(wifi_pct "$W_DL" "$W_PLAN")
      ui_row "$(t k_download)" "${C_B}$W_DL Mbps${C_R}  $(ui_bar "$(clamp "${pct:-0}")" 16) ${C_D}$(t wifi_of_plan "$pct" "$W_PLAN")${C_R}" "$( [ "${pct:-0}" -ge 60 ] && echo ok || echo warn )"
    else
      ui_row "$(t k_download)" "${C_B}$W_DL Mbps${C_R}" info
    fi
    ui_row "$(t k_upload)" "${W_UL:-—} Mbps" info
  else
    ui_row "$(t k_download)" "$(t wifi_speed_failed)" warn
  fi
  if [ -n "$W_R_MED" ]; then
    ui_row "$(t k_ping_router)" "$(t wifi_ping_val "$W_R_MED" "$W_R_MAX" "$W_R_JIT")" "$(wifi_has_jumps && echo warn || echo ok)"
  fi
  if [ -n "$W_I_MED" ]; then
    ui_row "$(t k_ping_net)" "$(t wifi_ping_val "$W_I_MED" "$W_I_MAX" "$W_I_JIT")" "$( [ "${W_I_SPIKES:-0}" -ge 2 ] && echo warn || echo ok )"
  else
    ui_row "$(t k_ping_net)" "$(t wifi_no_reply)" warn
  fi
  if wifi_has_jumps; then ui_note "     $(t wifi_jumps_note "$W_R_SPIKES")"; fi
  if [ -n "${L_DL:-}" ] && [ -n "$W_DL" ]; then
    local mark text
    IFS=$'\t' read -r mark text <<< "$(wifi_verdict_line "$L_DL" "$W_DL")"
    [ -n "$text" ] && ui_row "$(t k_since_last)" "$text  ${C_D}· ${L_DATE}${C_R}" "$mark"
  fi
  return 0
}

wifi_show_radio() {
  printf "\n  ${C_D}%s${C_R}\n" "$(t part_wifi_radio)"
  if [ -n "$W_CH" ]; then
    ui_row "$(t k_band)" "$(t wifi_band_val "$W_BAND" "$W_CH" "$W_WIDTH")" "$( [ "$W_BAND" = "2.4" ] && echo warn || echo ok )"
  fi
  if [ -n "$W_GEN" ]; then
    case "$W_GEN" in
      4|5) ui_row "$(t k_wifi_type)" "$(t wifi_gen_val "$W_GEN" "$W_PHY")  ${C_D}$(t wifi_gen_old)${C_R}" warn ;;
      *)   ui_row "$(t k_wifi_type)" "$(t wifi_gen_val "$W_GEN" "$W_PHY")" ok ;;
    esac
  fi
  if [ -n "$W_SIGNAL" ]; then
    local word st=ok
    if [ "$W_SIGNAL" -ge -55 ]; then word=$(t wifi_sig_excellent)
    elif [ "$W_SIGNAL" -ge -65 ]; then word=$(t wifi_sig_good)
    elif [ "$W_SIGNAL" -ge -70 ]; then word=$(t wifi_sig_fair); st=warn
    else word=$(t wifi_sig_weak); st=bad; fi
    ui_row "$(t k_signal)" "$(t wifi_signal_val "$W_SIGNAL" "$word" "${W_NOISE:-—}")" "$st"
  fi
  if [ -n "$W_CH" ]; then
    if [ "${W_SHARE:-0}" -eq 0 ]; then
      ui_row "$(t k_neighbors)" "$(t wifi_neighbors_none)" ok
    else
      ui_row "$(t k_neighbors)" "$(t wifi_neighbors_val "$W_SHARE")" "$(wifi_channel_fix && echo warn || echo info)"
      wifi_channel_fix && ui_note "     $(t wifi_best_val "$W_BEST" "$W_BEST_N")"
    fi
    [ -n "$W_CHANNELS" ] && ui_note "     $(t wifi_channels_val "$W_CHANNELS")"
  fi
  return 0
}

wifi_show_mac() {
  printf "\n  ${C_D}%s${C_R}\n" "$(t part_wifi_mac)"
  ui_row "DNS" "${W_DNS:-—}" info
  if [ -n "$W_VPN" ]; then ui_row "$(t k_vpn)" "$(t wifi_vpn_on "$W_VPN")" warn
  elif [ "$W_PROXY" = "1" ]; then ui_row "$(t k_vpn)" "$(t wifi_proxy_on)" warn
  else ui_row "$(t k_vpn)" "$(t off)" ok; fi
  ui_row "$(t k_lowpower)" "$( [ "$W_LOWPOWER" = "1" ] && t on || t off)" "$( [ "$W_LOWPOWER" = "1" ] && echo warn || echo ok)"
  ui_row "AirDrop" "$(wifi_airdrop_word "$W_AIRDROP")" "$(wifi_mark "$W_AIRDROP" everyone contacts)"
  ui_row "Handoff" "$(wifi_word "$W_HANDOFF")" "$(wifi_mark "$W_HANDOFF" on)"
  ui_row "$(t k_airplay)" "$(wifi_word "$W_AIRPLAY")" "$(wifi_mark "$W_AIRPLAY" on)"
  if [ -n "$W_APPS" ]; then
    ui_row "$(t k_busy_apps "$WIFI_APPS_SECONDS")" "$W_APPS" "$(awk -v m="$W_APPS_TOTAL" 'BEGIN { print (m >= 5 ? "warn" : "info") }')"
  else
    ui_row "$(t k_busy_apps "$WIFI_APPS_SECONDS")" "$(t wifi_apps_quiet)" ok
  fi
}

# The router that gives your Wi-Fi is not always the main router: a second
# router, mesh or access point can hang behind it (e.g. a TP-Link on the
# provider's box). After you say yes to the fix, MacUp pings each address of
# your network once and opens the start page of the devices that answer, the
# same as a browser would (no login, nothing is changed), to name them.
wifi_web_label() { # IP → "label<TAB>1 if a router brand was recognised"
  local raw low brand="" title realm label
  raw=$(curl -s -k -m 2 --noproxy '*' -L --max-redirs 2 -D - "http://$1/" 2>/dev/null | head -c 40000 | tr '\r\n\t' '   ') || raw=""
  [ -z "$raw" ] && return 0
  low=$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]')
  case "$low" in
    *tp-link*|*tplink*|*archer*|*"/webpages/"*|*"su/su.js"*) brand="TP-Link" ;;
    *zxhn*|*"zte corporation"*) brand="ZTE" ;;
    *fritz*) brand="FRITZ!Box" ;;
    *asuswrt*|*"asus router"*) brand="ASUS" ;;
    *netgear*) brand="NETGEAR" ;;
    *huawei*) brand="Huawei" ;;
    *mikrotik*|*routeros*) brand="MikroTik" ;;
    *unifi*|*ubiquiti*) brand="Ubiquiti" ;;
    *mercusys*) brand="Mercusys" ;;
    *tenda*) brand="Tenda" ;;
    *miwifi*) brand="Xiaomi" ;;
    *linksys*) brand="Linksys" ;;
    *keenetic*) brand="Keenetic" ;;
    *openwrt*) brand="OpenWrt" ;;
    *fiberhome*) brand="FiberHome" ;;
    *zyxel*) brand="Zyxel" ;;
    *d-link*|*dlink*) brand="D-Link" ;;
    *sagemcom*) brand="Sagemcom" ;;
    *technicolor*) brand="Technicolor" ;;
  esac
  title=$(printf '%s' "$raw" | sed -n 's/.*<[Tt][Ii][Tt][Ll][Ee][^>]*>\([^<]*\)<\/[Tt][Ii][Tt][Ll][Ee]>.*/\1/p' | head -1 | sed 's/^ *//; s/ *$//')
  realm=$(printf '%s' "$raw" | sed -n 's/.*[Rr]ealm="\([^"]*\)".*/\1/p' | head -1)
  label="${title:-$realm}"
  label="${label:0:40}"
  if [ -n "$brand" ]; then
    case "$label" in "") label="$brand" ;; *"$brand"*) ;; *) label="$brand · $label" ;; esac
    printf '%s\t1\n' "$label"
  else
    printf '%s\t0\n' "${label:-web page}"
  fi
}

wifi_find_routers() { # → $MACUP_TMP/wifi.routers: "ip<TAB>label<TAB>brand"
  local net="${W_ROUTER%.*}" mask ip i
  : > "$MACUP_TMP/wifi.routers"
  [ -n "$W_ROUTER" ] || return 0
  mask=$(ipconfig getoption "$W_DEV" subnet_mask 2>/dev/null) || mask=""
  if [ "$mask" = "255.255.255.0" ]; then
    for ((i = 1; i < 255; i++)); do ping -c1 -W 300 "$net.$i" >/dev/null 2>&1 & done
    wait
  fi
  arp -an 2>/dev/null | awk -v net="$net." '{
      ip = $2; gsub(/[()]/, "", ip)
      if (index(ip, net) == 1 && $4 ~ /:/ && $4 != "ff:ff:ff:ff:ff:ff") print ip }' |
    sort -u -t. -k4,4n > "$MACUP_TMP/wifi.lan"
  grep -qx "$W_ROUTER" "$MACUP_TMP/wifi.lan" || printf '%s\n' "$W_ROUTER" >> "$MACUP_TMP/wifi.lan"
  while read -r ip; do
    [ "$ip" = "$W_IP" ] && continue
    ( wifi_web_label "$ip" > "$MACUP_TMP/web.$ip" ) &
  done < "$MACUP_TMP/wifi.lan"
  wait
  sort -u -t. -k4,4n "$MACUP_TMP/wifi.lan" | while read -r ip; do
    [ -s "$MACUP_TMP/web.$ip" ] && printf '%s\t%s\n' "$ip" "$(cat "$MACUP_TMP/web.$ip")"
  done > "$MACUP_TMP/wifi.routers"
  return 0
}

# Lists the routers found and asks which one gives the Wi-Fi → address in $REPLY.
wifi_pick_router() {
  local n=0 def="" gw_n=1 ip label brand pick
  ui_spin "$(t wifi_router_finding)" wifi_find_routers
  if [ ! -s "$MACUP_TMP/wifi.routers" ]; then REPLY="$W_ROUTER"; return 0; fi
  ui_note "     $(t wifi_router_list_note)"
  while IFS=$'\t' read -r ip label brand; do
    n=$((n + 1))
    if [ "$ip" = "$W_ROUTER" ]; then gw_n=$n; label="$label · $(t wifi_router_main)"; fi
    # A second router (not the main one) is the likely source of the Wi-Fi.
    [ -z "$def" ] && [ "$ip" != "$W_ROUTER" ] && [ "$brand" = "1" ] && def=$n
    printf "     ${C_Y}%s${C_R}  %s  ${C_D}%s${C_R}\n" "$n" "$(ui_pad "$ip" 15)" "$label"
  done < "$MACUP_TMP/wifi.routers"
  # The main router is a provider's box (ZTE, Huawei…)? Then a second device
  # with a web page is most likely the Wi-Fi router plugged in behind it.
  if [ -z "$def" ] && [ "$n" -gt 1 ]; then
    case "$(sed -n "${gw_n}p" "$MACUP_TMP/wifi.routers" | cut -f2)" in
      ZTE*|Huawei*|FiberHome*|Sagemcom*|Technicolor*|Zyxel*|Nokia*)
        def=$(awk -F'\t' -v gw="$W_ROUTER" '$1 != gw { print NR; exit }' "$MACUP_TMP/wifi.routers") ;;
    esac
  fi
  [ -z "$def" ] && def=$gw_n
  [ "$n" -gt 1 ] && ui_note "     $(t wifi_router_hint)"
  pick=$def
  if [ "$n" -gt 1 ]; then
    ui_ask "$(t wifi_router_pick)" "$def"
    case "$REPLY" in ''|*[!0-9]*) ;; *) [ "$REPLY" -ge 1 ] && [ "$REPLY" -le "$n" ] && pick=$REPLY ;; esac
  fi
  REPLY=$(sed -n "${pick}p" "$MACUP_TMP/wifi.routers" | cut -f1)
  [ -z "$REPLY" ] && REPLY="$W_ROUTER"
  return 0
}

# The settings MacUp may ask you to change, written down before anything changes.
wifi_write_before() {
  mkdir -p "$WIFI_DIR" 2>/dev/null || return 1
  {
    printf 'MacUp %s — %s\n' "$(t wifi_title)" "$(t wifi_before_title)"
    printf '%s %s\n\n' "$(t wifi_saved_on)" "$(date '+%Y-%m-%d %H:%M')"
    printf 'AirDrop: %s\n' "$(wifi_airdrop_word "$W_AIRDROP")"
    printf 'Handoff: %s\n' "$(wifi_word "$W_HANDOFF")"
    printf '%s: %s\n' "$(t k_airplay)" "$(wifi_word "$W_AIRPLAY")"
    printf '%s: %s\n' "$(t k_lowpower)" "$( [ "$W_LOWPOWER" = "1" ] && t on || t off)"
    [ -n "$W_CH" ] && printf '%s: %s\n' "$(t wifi_router_channel)" "$(t wifi_band_val "$W_BAND" "$W_CH" "$W_WIDTH")"
    [ -n "$W_ROUTER" ] && printf '%s: http://%s\n' "$(t wifi_router_page)" "$W_ROUTER"
    printf '\n%s: %s Mbps\n' "$(t k_download)" "${W_DL:-—}"
    [ -n "$W_R_MED" ] && printf '%s: %s\n' "$(t k_ping_router)" "$(t wifi_ping_val "$W_R_MED" "$W_R_MAX" "$W_R_JIT")"
    [ -n "$W_I_MED" ] && printf '%s: %s\n' "$(t k_ping_net)" "$(t wifi_ping_val "$W_I_MED" "$W_I_MAX" "$W_I_JIT")"
  } > "$WIFI_BEFORE"
}

# wifi_verdict BEFORE AFTER → "up|same|down<TAB>percent" (10% either way counts)
wifi_verdict() {
  awk -v a="${1:-0}" -v b="${2:-}" 'BEGIN {
    if (a <= 0 || b == "") exit
    d = (b - a) * 100 / a
    printf "%s\t%.0f\n", (d >= 10 ? "up" : (d <= -10 ? "down" : "same")), d }'
}

# wifi_verdict_line BEFORE AFTER → "mark<TAB>text", e.g. "ok	Faster: 470 → 560 Mbps (+19%)"
wifi_verdict_line() {
  local kind pct
  IFS=$'\t' read -r kind pct <<< "$(wifi_verdict "$1" "$2")"
  case "$kind" in
    up)   printf 'ok\t%s\n' "$(t wifi_verdict_up "$1" "$2" "$pct")" ;;
    down) printf 'warn\t%s\n' "$(t wifi_verdict_down "$1" "$2" "$pct")" ;;
    same) printf 'info\t%s\n' "$(t wifi_verdict_same "$1" "$2")" ;;
  esac
}

wifi_read_last() {
  L_DATE=""; L_DL=""; L_RMAX=""
  [ -f "$WIFI_LAST" ] || return 0
  L_DATE=$(awk -F= '$1 == "date" { print substr($0, 6); exit }' "$WIFI_LAST")
  L_DL=$(awk -F= '$1 == "dl" && $2 ~ /^[0-9]+$/ { print $2; exit }' "$WIFI_LAST")
  L_RMAX=$(awk -F= '$1 == "rmax" && $2 ~ /^[0-9]+$/ { print $2; exit }' "$WIFI_LAST")
  return 0
}

wifi_write_last() {
  [ -n "$W_DL" ] || return 0
  mkdir -p "$WIFI_DIR" 2>/dev/null || return 0
  printf 'date=%s\ndl=%s\nrmax=%s\nrjit=%s\nchannel=%s\n' "$(date '+%Y-%m-%d %H:%M')" "$W_DL" "${W_R_MAX:-}" "${W_R_JIT:-}" "${W_CH:-}" > "$WIFI_LAST" 2>/dev/null || true
}

wifi_before_after() { # B_DL B_RMAX B_RJIT
  local up=""
  [ -n "$1" ] && [ -n "$W_DL" ] && [ "$1" -gt 0 ] && up=$(awk -v a="$1" -v b="$W_DL" 'BEGIN { d = (b - a) * 100 / a; printf "%s%.0f%%", (d >= 0 ? "▲ +" : "▼ "), d }')
  printf "\n  %s %s %s\n" "$(ui_pad "" 22)" "$(ui_pad "$(t wifi_before)" 14)" "$(t wifi_after)"
  printf "  %s %s ${C_B}%s${C_R}  ${C_Y}%s${C_R}\n" "$(ui_pad "$(t k_download)" 22)" "$(ui_pad "${1:-—} Mbps" 14)" "${W_DL:-—} Mbps" "$up"
  printf "  %s %s ${C_B}%s${C_R}\n" "$(ui_pad "$(t wifi_ping_worst)" 22)" "$(ui_pad "${2:-—} ms" 14)" "${W_R_MAX:-—} ms"
  printf "  %s %s ${C_B}%s${C_R}\n" "$(ui_pad "$(t wifi_jitter)" 22)" "$(ui_pad "${3:-—} ms" 14)" "${W_R_JIT:-—} ms"
  # The answer in one line: did the speed go up or not — and what is next.
  local mark text
  IFS=$'\t' read -r mark text <<< "$(wifi_verdict_line "$1" "$W_DL")"
  echo
  case "$mark" in
    ok)   printf "  ${C_B}✓  %s${C_R}\n" "$text" ;;
    warn) printf "  ${C_Y}▼  %s${C_R}\n" "$text"; ui_note "     $(t wifi_verdict_undo)" ;;
    info) printf "  ${C_B}≈  %s${C_R}\n" "$text" ;;
  esac
  if [ -n "$2" ] && [ -n "$W_R_MAX" ] && [ "$2" -ge 20 ] && [ "$W_R_MAX" -le $(( $2 * 7 / 10 )) ]; then
    printf "  ${C_B}✓  %s${C_R}\n" "$(t wifi_verdict_steadier "$2" "$W_R_MAX")"
  fi
  case "$W_GEN" in 4|5) [ "$mark" = "ok" ] || ui_note "     $(t wifi_verdict_router)" ;; esac
  return 0
}

wifi_fix() {
  local b_dl="$W_DL" b_rmax="$W_R_MAX" b_rjit="$W_R_JIT" changed=0
  ui_title "$(t wifi_fix_title)" "→"
  if wifi_write_before; then
    ui_row "$(t wifi_saved)" "${C_D}$WIFI_BEFORE${C_R}" ok
    ui_note "     $(t wifi_undo_hint)"
  fi
  if wifi_continuity_busy; then
    echo
    printf "  ${C_Y}1${C_R}  ${C_B}%s${C_R}\n" "$(t wifi_rec_awdl)"
    ui_note "     $(t wifi_switch_steps)"
    if ui_yes "$(t wifi_open_airdrop_q)" y; then
      open "$WIFI_PANE_AIRDROP" 2>/dev/null || open -b com.apple.systempreferences 2>/dev/null || true
      ui_pause "$(t wifi_done_enter)"
      wifi_read_continuity
      ui_row "AirDrop" "$(wifi_airdrop_word "$W_AIRDROP")" "$(wifi_mark "$W_AIRDROP" everyone contacts)"
      ui_row "Handoff" "$(wifi_word "$W_HANDOFF")" "$(wifi_mark "$W_HANDOFF" on)"
      ui_row "$(t k_airplay)" "$(wifi_word "$W_AIRPLAY")" "$(wifi_mark "$W_AIRPLAY" on)"
      changed=1
    fi
  fi
  if wifi_channel_fix; then
    echo
    printf "  ${C_Y}2${C_R}  ${C_B}%s${C_R}\n" "$(t wifi_rec_channel "$W_BEST" "$W_WIDTH")"
    local wifi_router=""
    wifi_pick_router; wifi_router="$REPLY"
    ui_note "     $(t wifi_router_steps "${wifi_router:-192.168.1.1}" "$W_BEST" "$W_WIDTH")"
    wifi_is_dfs "$W_BEST" && ui_note "     $(t wifi_rec_dfs)"
    if [ -n "$wifi_router" ] && ui_yes "$(t wifi_open_router_q)" y; then
      open "http://$wifi_router" 2>/dev/null || true
      ui_pause "$(t wifi_done_enter)"
      changed=1
    fi
  fi
  if [ "$W_LOWPOWER" = "1" ]; then
    echo
    printf "  ${C_Y}3${C_R}  ${C_B}%s${C_R}\n" "$(t wifi_rec_lowpower)"
    if ui_yes "$(t wifi_open_battery_q)" y; then
      open "$WIFI_PANE_BATTERY" 2>/dev/null || true
      ui_pause "$(t wifi_done_enter)"
      changed=1
    fi
  fi
  # Offer the test whenever a step was shown: some changes (like the router's
  # channel) are often made by hand in the browser.
  [ "$changed" = "1" ] || wifi_continuity_busy || wifi_channel_fix || [ "$W_LOWPOWER" = "1" ] || return 0
  if ui_yes "$(t wifi_retest_q)" y; then
    echo
    ui_spin "$(t wifi_checking)" wifi_measure_quiet
    wifi_load_state
    wifi_before_after "$b_dl" "$b_rmax" "$b_rjit"
    wifi_write_last
    {
      printf '\n%s (%s)\n' "$(t wifi_after)" "$(date '+%Y-%m-%d %H:%M')"
      printf '%s: %s Mbps\n' "$(t k_download)" "${W_DL:-—}"
      [ -n "$W_R_MED" ] && printf '%s: %s\n' "$(t k_ping_router)" "$(t wifi_ping_val "$W_R_MED" "$W_R_MAX" "$W_R_JIT")"
    } >> "$WIFI_BEFORE" 2>/dev/null
  fi
  return 0
}

wifi_collect_quiet() { wifi_collect; }
wifi_measure_quiet() { wifi_measure; }

cmd_wifi() {
  macup_tmp
  wifi_reset
  case "$W_PLAN" in *[!0-9]*|0*) W_PLAN="" ;; esac
  ui_title "$(t wifi_title)" "7"
  ui_note "$(t wifi_intro)"
  ui_note "$(t wifi_intro_net)"
  W_DEV=$(wifi_device)
  if [ -z "$W_DEV" ]; then echo; ui_row "Wi-Fi" "$(t wifi_no_wifi)" warn; return 0; fi
  W_IP=$(ipconfig getifaddr "$W_DEV" 2>/dev/null) || W_IP=""
  if [ -z "$W_IP" ]; then echo; ui_row "Wi-Fi" "$(t wifi_not_connected)" warn; return 0; fi
  W_ROUTER=$(ipconfig getoption "$W_DEV" router 2>/dev/null) || W_ROUTER=""
  if [ -z "$W_PLAN" ] && [ -t 0 ]; then
    ui_ask "$(t wifi_plan_q)" ""
    case "$REPLY" in *[!0-9]*|""|0*) ;; *) W_PLAN="$REPLY" ;; esac
  fi
  echo
  ui_spin "$(t wifi_checking)" wifi_collect_quiet
  wifi_load_state
  wifi_read_last
  [ -t 0 ] && wifi_write_last
  wifi_show_speed
  wifi_show_radio
  wifi_show_mac
  ui_title "$(t report_recs)" "→"
  wifi_recommendations
  show_recommendations
  case "$REC" in
    ok\|*) return 0 ;;
  esac
  if [ -t 0 ] && ui_yes "$(t wifi_fix_q)" y; then wifi_fix; fi
  return 0
}

cmd_wifi_undo() {
  ui_title "$(t wifi_undo_title)" "↺"
  if [ ! -f "$WIFI_BEFORE" ]; then ui_note "$(t wifi_undo_none)"; return 0; fi
  ui_note "$(t wifi_undo_intro)"
  echo
  sed 's/^/     /' "$WIFI_BEFORE"
  echo
  if [ -t 0 ] && ui_yes "$(t wifi_open_airdrop_q)" n; then
    open "$WIFI_PANE_AIRDROP" 2>/dev/null || open -b com.apple.systempreferences 2>/dev/null || true
  fi
  return 0
}
