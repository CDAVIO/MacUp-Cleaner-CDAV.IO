#!/bin/bash
# Renders an example MacUp PDF report (example values, not a real Mac) with
# the same code `macup check` uses:  bash docs/images/src/report_example.sh OUT.pdf
set -euo pipefail
MACUP_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
for f in ui i18n checks clean views report; do . "$MACUP_ROOT/lib/$f.sh"; done
i18n_load en
MACUP_TMP=$(mktemp -d); trap 'rm -rf "$MACUP_TMP"' EXIT

H_MODEL="MacBook Air"; H_CHIP="Apple M3"; H_MACOS="15.1"
H_CORES=8; H_PCORES=4; H_ECORES=4; H_UPTIME_DAYS=2
H_DISK_TOTAL=494384795648; H_DISK_FREE=63200000000; H_DISK_USED=$(( H_DISK_TOTAL - H_DISK_FREE )); H_DISK_FREE_PCT=12
H_SSD_MODEL="APPLE SSD AP0512Z"; H_SSD_SMART="Verified"; H_SSD_KIND="SSD"; H_SSD_WEAR=""
H_BAT=1; H_BAT_HEALTH=91; H_BAT_CYCLES=312; H_BAT_CONDITION="Normal"; H_BAT_CHARGE=78; H_BAT_CHARGING="TRUE"
H_MEM_TOTAL=17179869184; H_MEM_LABEL="16 GB"; H_MEM_FREE_PCT=38; H_SWAP_MB=410
H_CPU_LOAD_PCT=18; H_THERMAL_WARN=0
H_GPU="Apple M3"; H_GPU_CORES=10; H_GPU_METAL="Metal 3"; H_DISPLAYS="Color LCD (2560 x 1664 @ 60Hz)"
P_gatekeeper=1; P_sip=1; P_filevault=1; P_firewall=0; P_xprotect=1; P_responses=1; P_autoupdate=1; P_PASSED=6; P_TOTAL=7
H_XPROTECT_VERSION="5368"
H_STARTUP=9; H_STARTUP_BROKEN=0; H_STARTUP_LIST=""
H_TOP_CPU=$'Safari\t12.4\nPhotos\t6.1\nMail\t2.3'; H_TOP_MEM=$'Safari\t1932735283\nXcode\t1288490188'
H_CLEANABLE=8600000000

compute_scores
build_recommendations
build_html "$MACUP_TMP/report.html"
"$MACUP_ROOT/bin/macup-pdf" "$MACUP_TMP/report.html" "$1"
