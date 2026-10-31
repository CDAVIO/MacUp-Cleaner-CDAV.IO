#!/bin/bash
# MacUp — read-only health checks. Uses only tools that ship with macOS and
# never needs an administrator password. Results go into H_* variables.
# Bash 3.2 compatible.
# shellcheck disable=SC2059,SC2034  # colours in printf formats; H_* results are read by other files

# ── helpers ────────────────────────────────────────────────────────────────

# pj FILE KEYPATH → raw value from a JSON/plist file ("" when missing)
# Some macOS versions (e.g. 15) print "Could not extract value…" on stdout
# for a missing key, so the output is used only when plutil succeeded.
pj() {
  local v
  v=$(plutil -extract "$2" raw -o - "$1" 2>/dev/null) || return 0
  case "$v" in *"Could not extract value"*|*"No value at that key path"*) return 0 ;; esac
  printf '%s\n' "$v"
}

# Integer from text like "93%" or "24 GB"
num() { printf '%s' "$1" | tr -cd '0-9' | cut -c1-12; }

clamp() { local v="$1"; [ "$v" -lt 0 ] && v=0; [ "$v" -gt 100 ] && v=100; printf '%s' "$v"; }

macup_tmp() {
  [ -n "${MACUP_TMP:-}" ] && [ -d "$MACUP_TMP" ] && return 0
  MACUP_TMP=$(mktemp -d "${TMPDIR:-/tmp}/macup.XXXXXX")
  trap 'rm -rf "$MACUP_TMP"' EXIT
}

# ── collection ─────────────────────────────────────────────────────────────

collect_profile() {
  macup_tmp
  local sp="$MACUP_TMP/profile.json"
  [ -s "$sp" ] && return 0
  # -detailLevel mini leaves out serial numbers and other identifiers.
  system_profiler -json -detailLevel mini SPHardwareDataType SPPowerDataType \
    SPDisplaysDataType SPNVMeDataType SPSerialATADataType > "$sp" 2>/dev/null || true
}

collect_hardware() {
  collect_profile
  local sp="$MACUP_TMP/profile.json" procs
  H_MODEL=$(pj "$sp" SPHardwareDataType.0.machine_name)
  H_MODEL_ID=$(pj "$sp" SPHardwareDataType.0.machine_model)
  H_CHIP=$(pj "$sp" SPHardwareDataType.0.chip_type)
  [ -z "$H_CHIP" ] && H_CHIP=$(pj "$sp" SPHardwareDataType.0.cpu_type)
  [ -z "$H_CHIP" ] && H_CHIP=$(sysctl -n machdep.cpu.brand_string 2>/dev/null)
  [ -z "$H_MODEL" ] && H_MODEL="Mac"
  # Physical cores for display; logical CPUs (Intel Hyper-Threading counts
  # each core twice) for the load %.
  H_CORES=$(sysctl -n hw.physicalcpu 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null)
  H_THREADS=$(sysctl -n hw.logicalcpu 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null)
  H_PCORES=$(sysctl -n hw.perflevel0.physicalcpu 2>/dev/null || true)
  H_ECORES=$(sysctl -n hw.perflevel1.physicalcpu 2>/dev/null || true)
  procs=$(pj "$sp" SPHardwareDataType.0.number_processors)
  case "$procs" in proc\ *) H_CORES=$(printf '%s' "$procs" | cut -d' ' -f2 | cut -d: -f1) ;; esac
  # Show "P + E" only when it adds up (Intel has no core types; a future
  # chip with a third core type would not add up either).
  if [ -z "$H_PCORES" ] || [ -z "$H_ECORES" ] || [ "$(( H_PCORES + H_ECORES ))" != "${H_CORES:-0}" ]; then
    H_PCORES=""; H_ECORES=""
  fi
  H_MACOS=$(sw_vers -productVersion 2>/dev/null)
  H_BUILD=$(sw_vers -buildVersion 2>/dev/null)
  local boot now
  # "{ sec = 1793442307, usec = 528889 } …" — take sec, not usec.
  boot=$(sysctl -n kern.boottime 2>/dev/null | sed -n 's/^{ *sec = \([0-9]*\),.*/\1/p')
  now=$(date +%s)
  H_UPTIME_DAYS=0
  [ -n "$boot" ] && H_UPTIME_DAYS=$(( (now - boot) / 86400 ))
}

collect_storage() {
  macup_tmp
  local plist="" total="" free=""
  plist=$(diskutil info -plist / 2>/dev/null) || true
  if [ -n "$plist" ]; then
    printf '%s' "$plist" > "$MACUP_TMP/disk.plist" 2>/dev/null
    total=$(pj "$MACUP_TMP/disk.plist" APFSContainerSize)
    free=$(pj "$MACUP_TMP/disk.plist" APFSContainerFree)
    case "$total" in *[!0-9]*) total="" ;; esac
    case "$free" in *[!0-9]*) free="" ;; esac
  fi
  if [ -z "$total" ] || [ -z "$free" ]; then
    # Fallback: the Data volume as df sees it (1K blocks).
    read -r total free <<< "$(df -k /System/Volumes/Data 2>/dev/null | awk 'NR==2 {print $2*1024, $4*1024}')"
  fi
  H_DISK_TOTAL=${total:-0}
  H_DISK_FREE=${free:-0}
  H_DISK_USED=$(( H_DISK_TOTAL - H_DISK_FREE ))
  H_DISK_FREE_PCT=0
  [ "$H_DISK_TOTAL" -gt 0 ] && H_DISK_FREE_PCT=$(( H_DISK_FREE * 100 / H_DISK_TOTAL ))
}

collect_ssd() {
  collect_profile
  local sp="$MACUP_TMP/profile.json" i j medium
  H_SSD_MODEL=$(pj "$sp" SPNVMeDataType.0._items.0.device_model)
  H_SSD_SMART=$(pj "$sp" SPNVMeDataType.0._items.0.smart_status)
  H_SSD_KIND="SSD"
  if [ -z "$H_SSD_MODEL" ]; then
    # Older Intel Macs: SATA SSD or hard disk.
    for i in 0 1 2; do
      for j in 0 1 2; do
        medium=$(pj "$sp" "SPSerialATADataType.$i._items.$j.spsata_medium_type")
        [ -z "$medium" ] && continue
        H_SSD_MODEL=$(pj "$sp" "SPSerialATADataType.$i._items.$j.device_model")
        H_SSD_SMART=$(pj "$sp" "SPSerialATADataType.$i._items.$j.smart_status")
        case "$medium" in *[Ss]olid*) H_SSD_KIND="SSD" ;; *) H_SSD_KIND="HDD" ;; esac
        break 2
      done
    done
  fi
  [ -z "$H_SSD_SMART" ] && H_SSD_SMART=$(diskutil info disk0 2>/dev/null | sed -n 's/.*SMART Status: *//p' | head -1)
  # Wear level (life used) only exists through smartmontools, if installed.
  H_SSD_WEAR=""
  local smartctl
  smartctl=$(command -v smartctl 2>/dev/null || true)
  [ -z "$smartctl" ] && [ -x /opt/homebrew/bin/smartctl ] && smartctl=/opt/homebrew/bin/smartctl
  [ -z "$smartctl" ] && [ -x /usr/local/bin/smartctl ] && smartctl=/usr/local/bin/smartctl
  if [ -n "$smartctl" ]; then
    H_SSD_WEAR=$("$smartctl" -a disk0 2>/dev/null | sed -n 's/^Percentage Used: *\([0-9]*\)%.*/\1/p' | head -1)
  fi
  H_SSD_SMARTCTL=${smartctl:+1}
}

collect_battery() {
  collect_profile
  local sp="$MACUP_TMP/profile.json" i cyc
  H_BAT=0; H_BAT_HEALTH=""; H_BAT_CYCLES=""; H_BAT_CONDITION=""; H_BAT_CHARGE=""; H_BAT_CHARGING=""
  for i in 0 1 2 3 4 5; do
    cyc=$(pj "$sp" "SPPowerDataType.$i.sppower_battery_health_info.sppower_battery_cycle_count")
    [ -z "$cyc" ] && continue
    H_BAT=1
    H_BAT_CYCLES="$cyc"
    H_BAT_HEALTH=$(num "$(pj "$sp" "SPPowerDataType.$i.sppower_battery_health_info.sppower_battery_health_maximum_capacity")")
    H_BAT_CONDITION=$(pj "$sp" "SPPowerDataType.$i.sppower_battery_health_info.sppower_battery_health")
    H_BAT_CHARGE=$(pj "$sp" "SPPowerDataType.$i.sppower_battery_charge_info.sppower_battery_state_of_charge")
    H_BAT_CHARGING=$(pj "$sp" "SPPowerDataType.$i.sppower_battery_charge_info.sppower_battery_is_charging")
    break
  done
  if [ "$H_BAT" = "1" ] && [ -z "$H_BAT_HEALTH" ]; then
    # Older macOS: compute from the battery controller.
    local maxc design
    maxc=$(ioreg -rn AppleSmartBattery 2>/dev/null | sed -n 's/.*"AppleRawMaxCapacity" = \([0-9]*\).*/\1/p' | head -1)
    design=$(ioreg -rn AppleSmartBattery 2>/dev/null | sed -n 's/.*"DesignCapacity" = \([0-9]*\).*/\1/p' | head -1)
    [ -n "$maxc" ] && [ -n "$design" ] && [ "$design" -gt 0 ] && H_BAT_HEALTH=$(( maxc * 100 / design ))
  fi
}

collect_memory() {
  H_MEM_TOTAL=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
  # Memory is sold in binary gigabytes (24 GB = 24 × 1024³ bytes).
  H_MEM_LABEL="$(( H_MEM_TOTAL / 1073741824 )) GB"
  H_MEM_FREE_PCT=$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: *\([0-9]*\)%.*/\1/p' | tail -1)
  [ -z "$H_MEM_FREE_PCT" ] && H_MEM_FREE_PCT=50
  local swap
  swap=$(sysctl -n vm.swapusage 2>/dev/null | sed -n 's/.*used = *\([0-9.]*\)M.*/\1/p')
  H_SWAP_MB=$(printf '%.0f' "${swap:-0}")
}

collect_cpu() {
  local load
  load=$(sysctl -n vm.loadavg 2>/dev/null | tr -d '{}' | awk '{print $1}')
  H_LOAD1=${load:-0}
  local cores=${H_THREADS:-$(sysctl -n hw.ncpu 2>/dev/null)}
  H_CPU_LOAD_PCT=$(awk -v l="$H_LOAD1" -v c="${cores:-1}" 'BEGIN { p = l * 100 / c; if (p > 100) p = 100; printf "%d", p }')
  # Intel Macs report a CPU speed limit; Apple silicon reports warnings only.
  H_THERMAL_LIMIT=$(pmset -g therm 2>/dev/null | sed -n 's/.*CPU_Speed_Limit *= *\([0-9]*\).*/\1/p' | head -1)
  H_THERMAL_WARN=0
  pmset -g therm 2>/dev/null | grep -qi "warning level.*[0-9]" && H_THERMAL_WARN=1
  [ -n "$H_THERMAL_LIMIT" ] && [ "$H_THERMAL_LIMIT" -lt 100 ] && H_THERMAL_WARN=1
  return 0
}

collect_gpu() {
  collect_profile
  local sp="$MACUP_TMP/profile.json" metal g i name res model vram
  H_GPU=""; H_GPU_CORES=""; H_GPU_METAL=""; H_DISPLAYS=""
  # Intel Macs can have two GPUs (Intel + AMD); screens hang under either.
  for g in 0 1 2; do
    model=$(pj "$sp" "SPDisplaysDataType.$g.sppci_model")
    [ -z "$model" ] && break
    # Dedicated video memory only (integrated GPUs share the main RAM).
    vram=$(pj "$sp" "SPDisplaysDataType.$g.spdisplays_vram")
    [ -n "$vram" ] && model="$model ($vram)"
    H_GPU="${H_GPU}${H_GPU:+ + }$model"
    [ -z "$H_GPU_CORES" ] && H_GPU_CORES=$(pj "$sp" "SPDisplaysDataType.$g.sppci_cores")
    if [ -z "$H_GPU_METAL" ]; then
      metal=$(pj "$sp" "SPDisplaysDataType.$g.spdisplays_mtlgpufamilysupport")
      H_GPU_METAL=$(printf '%s' "$metal" | sed 's/spdisplays_metal/Metal /')
    fi
    for i in 0 1 2 3; do
      name=$(pj "$sp" "SPDisplaysDataType.$g.spdisplays_ndrvs.$i._name")
      [ -z "$name" ] && break
      res=$(pj "$sp" "SPDisplaysDataType.$g.spdisplays_ndrvs.$i._spdisplays_resolution")
      H_DISPLAYS="${H_DISPLAYS}${H_DISPLAYS:+ · }$name${res:+ ($res)}"
    done
  done
  [ -z "$H_GPU" ] && H_GPU="$H_CHIP"
  return 0
}

# Protection: built-in macOS security, read-only. P_<id>=1 on, 0 off.
collect_protection() {
  local prefs="/Library/Preferences/com.apple.SoftwareUpdate"
  P_gatekeeper=0; P_sip=0; P_filevault=0; P_firewall=0; P_xprotect=1; P_responses=1; P_autoupdate=0
  spctl --status 2>/dev/null | grep -q "enabled" && P_gatekeeper=1
  csrutil status 2>/dev/null | grep -qi "enabled" && P_sip=1
  fdesetup status 2>/dev/null | grep -q "FileVault is On" && P_filevault=1
  /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null | grep -qi "enabled" && P_firewall=1
  [ "$(defaults read "$prefs" ConfigDataInstall 2>/dev/null)" = "0" ] && P_xprotect=0
  [ "$(defaults read "$prefs" CriticalUpdateInstall 2>/dev/null)" = "0" ] && P_responses=0
  [ "$(defaults read "$prefs" AutomaticallyInstallMacOSUpdates 2>/dev/null)" = "1" ] && P_autoupdate=1
  H_XPROTECT_VERSION=$(defaults read /Library/Apple/System/Library/CoreServices/XProtect.bundle/Contents/Info.plist CFBundleShortVersionString 2>/dev/null || true)
  P_PASSED=$(( P_gatekeeper + P_sip + P_filevault + P_firewall + P_xprotect + P_responses + P_autoupdate ))
  P_TOTAL=7
}

# Startup items (LaunchAgents/Daemons) and the busiest apps.
collect_performance() {
  H_STARTUP=0; H_STARTUP_BROKEN=0; H_STARTUP_LIST=""
  local dir plist prog label
  for dir in "$HOME/Library/LaunchAgents" /Library/LaunchAgents /Library/LaunchDaemons; do
    [ -d "$dir" ] || continue
    for plist in "$dir"/*.plist; do
      [ -f "$plist" ] || continue
      H_STARTUP=$((H_STARTUP + 1))
      prog=$(pj "$plist" Program)
      [ -z "$prog" ] && prog=$(pj "$plist" ProgramArguments.0)
      label=$(pj "$plist" Label)
      if [ -n "$prog" ] && [ "${prog#/}" != "$prog" ] && [ ! -e "$prog" ]; then
        H_STARTUP_BROKEN=$((H_STARTUP_BROKEN + 1))
        H_STARTUP_LIST="${H_STARTUP_LIST}${label:-$(basename "$plist" .plist)}"$'\n'
      fi
    done
  done
  H_TOP_CPU=$(ps -Aceo pcpu=,comm= -r 2>/dev/null | head -5 | awk '{ c=$1; $1=""; sub(/^ /,""); printf "%s\t%.1f\n", $0, c }')
  H_TOP_MEM=$(ps -Aceo rss=,comm= -m 2>/dev/null | head -5 | awk '{ m=$1; $1=""; sub(/^ /,""); printf "%s\t%d\n", $0, m*1024 }')
}

# Hidden caches MacUp can safely move to the Trash (see lib/clean.sh).
# The cache scan is the slowest part, so it starts first and runs in the
# background while the other checks run; collect_cleanable_finish waits for it.
collect_cleanable_start() {
  macup_tmp
  clean_scan "$MACUP_TMP/scan" >/dev/null 2>&1 &
  CLEAN_SCAN_PID=$!
}
collect_cleanable_finish() {
  [ -n "${CLEAN_SCAN_PID:-}" ] && wait "$CLEAN_SCAN_PID" 2>/dev/null
  CLEAN_SCAN_PID=""
  H_CLEANABLE=$(clean_total "$MACUP_TMP/scan")
}
collect_cleanable() { collect_cleanable_start; collect_cleanable_finish; }

# progress KEY → shows which part is being checked next to the spinner.
progress() { [ -n "${MACUP_TMP:-}" ] && printf '%s' "$(t "$1")" > "$MACUP_TMP/progress" 2>/dev/null; return 0; }

smart_state() { case "$H_SSD_SMART" in *[Vv]erified*) echo ok ;; *) echo warn ;; esac; }

# ── scores (0–100; "" when the part does not exist on this Mac) ─────────────

score_storage() {
  local f="$H_DISK_FREE_PCT"
  if   [ "$f" -ge 25 ]; then echo 100
  elif [ "$f" -ge 15 ]; then echo $(( 80 + (f - 15) * 2 ))
  elif [ "$f" -ge 10 ]; then echo $(( 60 + (f - 10) * 4 ))
  elif [ "$f" -ge 5 ];  then echo $(( 30 + (f - 5) * 6 ))
  else echo $(( 10 + f * 4 )); fi
}

score_ssd() {
  case "$H_SSD_SMART" in
    *[Ff]ail*) echo 10; return ;;
  esac
  if [ -n "$H_SSD_WEAR" ]; then clamp $(( 100 - H_SSD_WEAR )); return; fi
  case "$H_SSD_SMART" in Verified|*[Vv]erified*) echo 100 ;; *) echo "" ;; esac
}

score_battery() {
  [ "$H_BAT" = "1" ] || { echo ""; return; }
  local s="${H_BAT_HEALTH:-100}"
  case "$H_BAT_CONDITION" in *[Ss]ervice*|*[Rr]eplace*) [ "$s" -gt 55 ] && s=55 ;; esac
  clamp "$s"
}

score_memory() {
  local f="$H_MEM_FREE_PCT" s
  if   [ "$f" -ge 30 ]; then s=100
  elif [ "$f" -ge 15 ]; then s=$(( 75 + (f - 15) * 25 / 15 ))
  elif [ "$f" -ge 5 ];  then s=$(( 45 + (f - 5) * 3 ))
  else s=30; fi
  # Heavy swap use means the Mac often runs out of memory.
  if   [ "$H_SWAP_MB" -gt 8192 ]; then s=$(( s - 25 ))
  elif [ "$H_SWAP_MB" -gt 2048 ]; then s=$(( s - 10 )); fi
  clamp "$s"
}

score_cpu() {
  local s=100
  [ "$H_CPU_LOAD_PCT" -gt 90 ] && s=70
  [ "$H_CPU_LOAD_PCT" -gt 70 ] && [ "$s" -gt 85 ] && s=85
  [ "$H_THERMAL_WARN" = "1" ] && s=$(( s - 25 ))
  [ "$H_UPTIME_DAYS" -gt 30 ] && s=$(( s - 5 ))
  clamp "$s"
}

score_protection() { echo $(( P_PASSED * 100 / P_TOTAL )); }

score_cleanup() {
  local gb=$(( ${H_CLEANABLE:-0} / 1000000000 ))
  if   [ "$gb" -lt 2 ];  then echo 100
  elif [ "$gb" -lt 5 ];  then echo 92
  elif [ "$gb" -lt 10 ]; then echo 85
  elif [ "$gb" -lt 20 ]; then echo 75
  else echo 65; fi
}

# Weighted total of the parts that exist on this Mac.
compute_scores() {
  S_STORAGE=$(score_storage); S_SSD=$(score_ssd); S_BATTERY=$(score_battery)
  S_MEMORY=$(score_memory); S_CPU=$(score_cpu); S_PROTECTION=$(score_protection)
  S_CLEANUP=$(score_cleanup)
  compute_hero
}

# part_state SCORE → ok | warn | bad, or none when the part isn't on this Mac.
part_state() {
  if [ -z "$1" ]; then echo none; elif [ "$1" -ge 80 ]; then echo ok; elif [ "$1" -ge 55 ]; then echo warn; else echo bad; fi
}

# The one big number: battery health, like on iPhone. Macs without a battery
# (iMac, Mac mini, Mac Studio, Mac Pro) show the SSD instead.
compute_hero() {
  if [ "$H_BAT" = "1" ] && [ -n "$H_BAT_HEALTH" ]; then
    HERO_LABEL=$(t battery_health)
    HERO_PCT="$H_BAT_HEALTH"
    HERO_NOTE="$(t k_cycles): ${H_BAT_CYCLES:-—}$(bat_service_note)"
    HERO_STATE=$(part_state "$S_BATTERY")
  else
    HERO_LABEL=$(t part_ssd)
    HERO_PCT=""
    [ -n "$H_SSD_WEAR" ] && HERO_PCT=$(( 100 - H_SSD_WEAR ))
    HERO_NOTE="S.M.A.R.T.: ${H_SSD_SMART:-—}"
    HERO_STATE=$(part_state "$S_SSD")
  fi
  [ "$HERO_STATE" = "none" ] && HERO_STATE=ok
  return 0
}

# " · Service Recommended" only when Apple asks for a battery service
# (a normal battery would otherwise show "Good" twice).
bat_service_note() {
  case "$H_BAT_CONDITION" in *[Ss]ervice*|*[Rr]eplace*|*[Pp]oor*) printf ' · %s' "$H_BAT_CONDITION" ;; esac
}

# state_word ok|warn|bad → "Good" / "Needs attention"
state_word() { case "$1" in ok) t grade_good ;; none) printf '—' ;; *) t grade_attention ;; esac; }

collect_all() {
  collect_cleanable_start
  progress part_storage;     collect_hardware; collect_storage
  progress part_ssd;         collect_ssd
  progress part_battery;     collect_battery
  progress part_memory;      collect_memory
  progress part_cpu;         collect_cpu
  progress part_gpu;         collect_gpu
  progress part_protection;  collect_protection
  progress part_performance; collect_performance
  progress part_cleanup;     collect_cleanable_finish
  compute_scores
}
