#!/bin/bash
# MacUp — "This Mac", "Protection" and "Performance" screens (read-only).
# shellcheck disable=SC2059,SC2034  # colours in printf formats; H_* results are read by other files

cmd_mac() {
  macup_tmp
  ui_title "$(t mac_title)" "2"
  ui_spin "$(t checking)" collect_mac_quiet
  load_collected
  local cores="$H_CORES" bat_status ssd_health
  [ -n "$H_PCORES" ] && [ -n "$H_ECORES" ] && cores=$(t cores_split "$H_CORES" "$H_PCORES" "$H_ECORES")
  printf "  ${C_B}%s${C_R}  ${C_D}%s · macOS %s${C_R}\n\n" "$H_MODEL" "$H_CHIP" "$H_MACOS"

  printf "  ${C_D}%s${C_R}\n" "$(t part_storage)"
  ui_row "$(t k_used)" "$(ui_bar $(( 100 - H_DISK_FREE_PCT )) 20) $(ui_size "$H_DISK_USED") / $(ui_size "$H_DISK_TOTAL")" ""
  ui_row "$(t k_free)" "${C_B}$(ui_size "$H_DISK_FREE")${C_R}  ${C_D}($H_DISK_FREE_PCT%)${C_R}" "$( [ "$H_DISK_FREE_PCT" -ge 15 ] && echo ok || echo warn )"
  ui_row "$(t k_hidden_cache)" "$(ui_size "${H_CLEANABLE:-0}")" "$( [ "${H_CLEANABLE:-0}" -lt 2000000000 ] && echo ok || echo warn )"

  printf "\n  ${C_D}%s${C_R}\n" "$(t part_ssd)"
  ui_row "$(t k_model)" "${H_SSD_MODEL:-—} ($H_SSD_KIND)" info
  ui_row "S.M.A.R.T." "${H_SSD_SMART:-—}" "$(smart_state)"
  if [ -n "$H_SSD_WEAR" ]; then
    ssd_health=$(( 100 - H_SSD_WEAR ))
    ui_row "$(t k_ssd_health)" "$(ui_bar "$ssd_health" 20) ${C_B}$ssd_health%${C_R}" "$( [ "$ssd_health" -ge 80 ] && echo ok || echo warn )"
  else
    ui_row "$(t k_ssd_health)" "${C_D}$(t ssd_wear_unknown_short)${C_R}" info
  fi

  printf "\n  ${C_D}%s${C_R}\n" "$(t part_battery)"
  if [ "$H_BAT" = "1" ]; then
    bat_status=ok; [ -n "$H_BAT_HEALTH" ] && [ "$H_BAT_HEALTH" -lt 80 ] && bat_status=warn
    ui_row "$(t k_bat_health)" "$(ui_bar "${H_BAT_HEALTH:-0}" 20) ${C_B}${H_BAT_HEALTH:-—}%${C_R}  ${C_D}${H_BAT_CONDITION}${C_R}" "$bat_status"
    ui_row "$(t k_cycles)" "${H_BAT_CYCLES:-—}  ${C_D}$(t cycles_hint)${C_R}" info
    ui_row "$(t k_charge)" "$(ui_bar "${H_BAT_CHARGE:-0}" 20) ${H_BAT_CHARGE:-—}%$( [ "$H_BAT_CHARGING" = "TRUE" ] && printf '  %s' "$(t charging)")" info
  else
    ui_row "$(t part_battery)" "$(t no_battery)" info
  fi

  printf "\n  ${C_D}%s${C_R}\n" "$(t part_memory)"
  ui_row "$(t k_ram)" "$H_MEM_LABEL" info
  ui_row "$(t k_mem_free)" "$(ui_bar "$H_MEM_FREE_PCT" 20) $H_MEM_FREE_PCT%" "$( [ "$H_MEM_FREE_PCT" -ge 15 ] && echo ok || echo warn )"
  ui_row "$(t k_swap)" "$(awk -v m="$H_SWAP_MB" 'BEGIN { printf "%.1f GB", m / 1024 }')" "$( [ "$H_SWAP_MB" -le 2048 ] && echo ok || echo warn )"

  printf "\n  ${C_D}%s${C_R}\n" "$(t part_cpu)"
  ui_row "$(t k_chip)" "$H_CHIP" info
  ui_row "$(t k_cores)" "$cores" info
  ui_row "$(t k_load)" "$(ui_bar "$H_CPU_LOAD_PCT" 20) $H_CPU_LOAD_PCT%" "$( [ "$H_CPU_LOAD_PCT" -le 70 ] && echo ok || echo warn )"
  ui_row "$(t k_heat)" "$( [ "$H_THERMAL_WARN" = "1" ] && t heat_warn || t heat_ok )" "$( [ "$H_THERMAL_WARN" = "1" ] && echo warn || echo ok )"
  ui_row "$(t k_uptime)" "$(t days "$H_UPTIME_DAYS")" "$( [ "$H_UPTIME_DAYS" -le 14 ] && echo ok || echo warn )"

  printf "\n  ${C_D}%s${C_R}\n" "$(t part_gpu)"
  ui_row "$(t k_gpu)" "${H_GPU:-—}${H_GPU_CORES:+ · $(t gpu_cores "$H_GPU_CORES")}" info
  ui_row "Metal" "${H_GPU_METAL:-—}" info
  [ -n "$H_DISPLAYS" ] && ui_row "$(t k_displays)" "$H_DISPLAYS" info
  echo
  ui_note "$(t mac_tip)"
}

cmd_protection() {
  macup_tmp
  ui_title "$(t protection_title)" "3"
  ui_note "$(t protection_intro)"
  echo
  collect_protection
  local st
  prot_row() { if [ "$2" = "1" ]; then ui_row "$1" "${C_B}$(t on)${C_R}  ${C_D}$3${C_R}" ok; else ui_row "$1" "${C_Y}$(t off)${C_R}  ${C_D}$4${C_R}" warn; fi; }
  prot_row "Gatekeeper" "$P_gatekeeper" "$(t p_gatekeeper_d)" "$(t fix_gatekeeper)"
  prot_row "$(t p_sip)" "$P_sip" "$(t p_sip_d)" "$(t fix_sip)"
  prot_row "FileVault" "$P_filevault" "$(t p_filevault_d)" "$(t fix_filevault)"
  prot_row "$(t p_firewall)" "$P_firewall" "$(t p_firewall_d)" "$(t fix_firewall)"
  prot_row "XProtect" "$P_xprotect" "$(t p_xprotect_d "${H_XPROTECT_VERSION:-—}")" "$(t fix_updates)"
  prot_row "$(t p_responses)" "$P_responses" "$(t p_responses_d)" "$(t fix_updates)"
  prot_row "$(t p_autoupdate)" "$P_autoupdate" "$(t p_autoupdate_d)" "$(t fix_updates)"
  ui_line
  st=$(( P_PASSED * 100 / P_TOTAL ))
  printf "  %s  %s  ${C_B}%s/%s${C_R}\n" "$(ui_pad "$(t part_protection)" 22)" "$(ui_bar "$st" 24)" "$P_PASSED" "$P_TOTAL"
  echo
  ui_note "$(t antivirus_note_1)"
  ui_note "$(t antivirus_note_2)"
  if [ "$P_PASSED" -lt "$P_TOTAL" ] && ui_yes "$(t open_security_q)" n; then
    open "x-apple.systempreferences:com.apple.preference.security" 2>/dev/null || true
  fi
}

cmd_performance() {
  macup_tmp
  ui_title "$(t performance_title)" "4"
  collect_hardware; collect_memory; collect_cpu; collect_performance
  local name val
  ui_row "$(t k_load)" "$(ui_bar "$H_CPU_LOAD_PCT" 20) $H_CPU_LOAD_PCT%" "$( [ "$H_CPU_LOAD_PCT" -le 70 ] && echo ok || echo warn )"
  ui_row "$(t k_mem_free)" "$(ui_bar "$H_MEM_FREE_PCT" 20) $H_MEM_FREE_PCT%" "$( [ "$H_MEM_FREE_PCT" -ge 15 ] && echo ok || echo warn )"
  ui_row "$(t k_swap)" "$(awk -v m="$H_SWAP_MB" 'BEGIN { printf "%.1f GB", m / 1024 }')" "$( [ "$H_SWAP_MB" -le 2048 ] && echo ok || echo warn )"
  ui_row "$(t k_uptime)" "$(t days "$H_UPTIME_DAYS")" "$( [ "$H_UPTIME_DAYS" -le 14 ] && echo ok || echo warn )"

  printf "\n  ${C_D}%s${C_R}\n" "$(t top_cpu)"
  printf '%s\n' "$H_TOP_CPU" | while IFS=$'\t' read -r name val; do
    [ -n "$name" ] && printf "  %s ${C_B}%6s%%${C_R}\n" "$(ui_pad "  ${name:0:30}" 34)" "$val"
  done
  printf "\n  ${C_D}%s${C_R}\n" "$(t top_memory)"
  printf '%s\n' "$H_TOP_MEM" | while IFS=$'\t' read -r name val; do
    [ -n "$name" ] && printf "  %s ${C_B}%9s${C_R}\n" "$(ui_pad "  ${name:0:30}" 34)" "$(ui_size "$val")"
  done
  printf "\n  ${C_D}%s${C_R}\n" "$(t k_startup)"
  ui_row "$(t k_startup)" "$H_STARTUP" info
  ui_row "$(t k_startup_broken)" "$H_STARTUP_BROKEN" "$( [ "$H_STARTUP_BROKEN" -eq 0 ] && echo ok || echo warn )"
  if [ "$H_STARTUP_BROKEN" -gt 0 ]; then
    printf '%s' "$H_STARTUP_LIST" | head -5 | while IFS= read -r name; do [ -n "$name" ] && ui_note "     · $name"; done
    ui_note "$(t startup_broken_hint)"
  fi
  echo
  ui_note "$(t perf_tip)"
}

collect_mac_quiet() {
  collect_cleanable_start
  progress part_storage; collect_hardware; collect_storage
  progress part_ssd;     collect_ssd
  progress part_battery; collect_battery
  progress part_memory;  collect_memory
  progress part_cpu;     collect_cpu
  progress part_gpu;     collect_gpu
  progress part_cleanup; collect_cleanable_finish
  local v
  for v in $(compgen -v | grep -E '^H_'); do printf '%s=%q\n' "$v" "${!v}"; done > "$MACUP_TMP/collected.sh"
}
