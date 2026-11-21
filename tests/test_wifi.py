"""Tests for 7 · Wi-Fi Check (lib/wifi.sh).

macOS tools are replaced by shell functions with recorded output, so these
tests run anywhere. The system_profiler text below is a real Mac's output
(network names are hidden by macOS itself; hardware addresses removed).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SP_TEXT = """Wi-Fi:

      Software Versions:
          CoreWLAN: 16.0 (1657)
      Interfaces:
        en0:
          Card Type: Wi-Fi  (0x14E4, 0x4388)
          Firmware Version: wl0: Aug 26 2026 version 23.10.1042
IO80211_driverkit-1587.10 "IO80211_driverkit-1587.10" Oct  3 2026 14:53:06
          MAC Address: aa:bb:cc:dd:ee:ff
          Locale: Unknown
          Country Code: RO
          Supported PHY Modes: 802.11 a/b/g/n/ac/ax
          Supported Channels: 1 (2GHz), 6 (2GHz), 36 (5GHz), 100 (5GHz), 1 (6GHz)
          Wake On Wireless: Supported
          AirDrop: Supported
          Status: Connected
          Current Network Information:
            <redacted>:
              PHY Mode: 802.11ac
              Channel: 36 (5GHz, 80MHz)
              Country Code: RO
              Network Type: Infrastructure
              Security: WPA2 Personal
              Signal / Noise: -49 dBm / -94 dBm
              Transmit Rate: 173
              MCS Index: 9
          Other Local Wi-Fi Networks:
            <redacted>:
              PHY Mode: 802.11a/n/ac/ax
              Channel: 36 (5GHz, 80MHz)
              Network Type: Infrastructure
              Security: WPA/WPA2 Personal
            <redacted>:
              PHY Mode: 802.11b/g/n
              Channel: 11 (2GHz, 20MHz)
              Network Type: Infrastructure
              Security: WPA/WPA2 Personal
            <redacted>:
              PHY Mode: 802.11a/n/ac/ax
              Channel: 36 (5GHz, 80MHz)
              Network Type: Infrastructure
              Security: WPA2 Personal
            <redacted>:
              PHY Mode: 802.11a/n/ac/ax
              Channel: 44 (5GHz, 80MHz)
              Network Type: Infrastructure
              Security: WPA2/WPA3 Personal
            <redacted>:
              PHY Mode: 802.11b/g/n
              Channel: 9 (2GHz, 20MHz)
              Network Type: Infrastructure
              Security: WPA2 Personal
            <redacted>:
              PHY Mode: 802.11b/g/n
              Channel: 6 (2GHz, 20MHz)
              Network Type: Infrastructure
              Security: WPA2 Personal
            <redacted>:
              PHY Mode: 802.11b/g/n
              Channel: 1 (2GHz, 20MHz)
              Network Type: Infrastructure
              Security: WPA2 Personal
            <redacted>:
              PHY Mode: 802.11b/g/n
              Channel: 11 (2GHz, 20MHz)
              Network Type: Infrastructure
              Security: WPA2 Personal
            <redacted>:
              PHY Mode: 802.11b/g/n
              Channel: 1 (2GHz, 20MHz)
              Network Type: Infrastructure
              Security: WPA/WPA2 Personal
            <redacted>:
              PHY Mode: 802.11b/g/n
              Channel: 1 (2GHz, 20MHz)
              Network Type: Infrastructure
              Security: WPA/WPA2 Personal
            <redacted>:
              PHY Mode: 802.11b/g/n
              Channel: 6 (2GHz, 20MHz)
              Network Type: Infrastructure
              Security: WPA/WPA2 Personal
            <redacted>:
              PHY Mode: 802.11a/n/ac/ax
              Channel: 44 (5GHz, 80MHz)
              Network Type: Infrastructure
              Security: WPA2/WPA3 Personal
            <redacted>:
              PHY Mode: 802.11b/g/n
              Channel: 6 (2GHz, 20MHz)
              Network Type: Infrastructure
              Security: WPA/WPA2 Personal
            <redacted>:
              PHY Mode: 802.11a/n/ac
              Channel: 36 (5GHz, 80MHz)
              Network Type: Infrastructure
              Security: WPA2 Personal
              Signal / Noise: -45 dBm / -94 dBm
            <redacted>:
              PHY Mode: 802.11a/n/ac/ax
              Channel: 56 (5GHz, 160MHz)
              Network Type: Infrastructure
              Security: WPA2 Personal
        awdl0:
          MAC Address: aa:bb:cc:dd:ee:00
          Current Network Information:
              Network Type: Infrastructure
"""

# The same Mac as JSON (system_profiler -json SPAirPortDataType).
def _net(ch, phy, sec, sn=None, name="<redacted>"):
    d = {"_name": name, "spairport_network_channel": ch, "spairport_network_phymode": phy,
         "spairport_network_type": "spairport_network_type_station",
         "spairport_security_mode": sec}
    if sn:
        d["spairport_signal_noise"] = sn
    return d


WPA2 = "spairport_security_mode_wpa2_personal"
MIXED = "spairport_security_mode_wpa1_wpa2_personal"
SP_JSON = {"SPAirPortDataType": [{"spairport_airport_interfaces": [
    {"_name": "en0",
     "spairport_status_information": "spairport_status_connected",
     "spairport_current_network_information": {
         "_name": "<redacted>", "spairport_network_channel": "36 (5GHz, 80MHz)",
         "spairport_network_country_code": "RO", "spairport_network_mcs": 9,
         "spairport_network_phymode": "802.11ac", "spairport_network_rate": 173,
         "spairport_network_type": "spairport_network_type_station",
         "spairport_security_mode": WPA2, "spairport_signal_noise": "-49 dBm / -94 dBm"},
     "spairport_airport_other_local_wireless_networks": [
         _net("36 (5GHz, 80MHz)", "802.11a/n/ac/ax", MIXED),
         _net("11 (2GHz, 20MHz)", "802.11b/g/n", MIXED),
         _net("36 (5GHz, 80MHz)", "802.11a/n/ac/ax", WPA2),
         _net("44 (5GHz, 80MHz)", "802.11a/n/ac/ax", "spairport_security_mode_wpa2_wpa3_personal"),
         _net("6 (2GHz, 20MHz)", "802.11b/g/n", WPA2),
         _net("1 (2GHz, 20MHz)", "802.11b/g/n", WPA2),
         _net("44 (5GHz, 80MHz)", "802.11a/n/ac/ax", "spairport_security_mode_wpa2_wpa3_personal"),
         _net("36 (5GHz, 80MHz)", "802.11a/n/ac", WPA2, "-45 dBm / -94 dBm"),
         _net("56 (5GHz, 160MHz)", "802.11a/n/ac/ax", WPA2),
     ]},
    {"_name": "awdl0"},
]}]}

# Real router ping from the same Mac: 3–5 ms, with a jump about once a second.
PING_ROUTER = [6.970, 4.380, 11.515, 21.038, 3.824, 3.187, 3.918, 3.535, 47.541, 4.194,
               3.222, 11.059, 4.501, 80.546, 4.594, 3.686, 3.687, 3.555, 4.441, 3.955,
               3.751, 26.128, 3.897, 5.303, 4.102, 4.039, 59.327, 4.676, 4.542, 3.514,
               5.100, 85.465, 4.482, 4.153, 5.069, 5.906, 7.508, 4.664, 3.590, 35.768]
PING_CALM = [4.1, 3.9, 4.0, 4.2, 3.8, 4.0, 4.1, 3.9, 4.0, 4.3]


def ping_text(host, values):
    lines = [f"PING {host} ({host}): 56 data bytes"]
    lines += [f"64 bytes from {host}: icmp_seq={i} ttl=64 time={v:.3f} ms" for i, v in enumerate(values)]
    lines += ["", f"--- {host} ping statistics ---",
              f"{len(values)} packets transmitted, {len(values)} packets received, 0.0% packet loss"]
    return "\n".join(lines) + "\n"


# Stand-in for macOS plutil -extract KEYPATH raw|json -o - FILE (JSON files only).
FAKE_PLUTIL = r'''
import json, sys
a = sys.argv[1:]
key, fmt, path = a[a.index("-extract") + 1], a[a.index("-extract") + 2], a[-1]
try:
    v = json.load(open(path))
    for part in key.split("."):
        v = v[int(part)] if isinstance(v, list) else v[part]
except Exception:
    sys.stderr.write("Could not extract value\n"); sys.exit(1)
if fmt == "raw":
    if isinstance(v, (dict, list)):
        sys.exit(1)
    print(str(v).lower() if isinstance(v, bool) else v)
else:
    print(json.dumps(v, separators=(",", ":")).replace("/", "\\/"))
'''


def run_bash(tmp_path, body):
    (tmp_path / "plutil.py").write_text(FAKE_PLUTIL)
    fake_plutil = "" if shutil.which("plutil") else f'plutil() {{ "{sys.executable}" "{tmp_path}/plutil.py" "$@"; }}'
    script = f'''
set -uo pipefail
MACUP_ROOT="{ROOT}"
. "{ROOT}/lib/ui.sh"; . "{ROOT}/lib/i18n.sh"; . "{ROOT}/lib/checks.sh"; . "{ROOT}/lib/report.sh"; . "{ROOT}/lib/wifi.sh"
i18n_load en
MACUP_TMP="{tmp_path}"
HOME="{tmp_path}"
WIFI_DIR="{tmp_path}/state"; WIFI_BEFORE="{tmp_path}/state/wifi-before.txt"; WIFI_LAST="{tmp_path}/state/wifi-last.txt"
{fake_plutil}
{body}
'''
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr + out.stdout
    assert "unbound variable" not in out.stderr and "command not found" not in out.stderr, out.stderr
    return out.stdout


def analysis(tmp_path, nets_cmd, country="RO"):
    out = run_bash(tmp_path, f'{nets_cmd} > "$MACUP_TMP/nets"; wifi_analyze {country} < "$MACUP_TMP/nets"')
    first, *chans = out.strip().splitlines()
    return first.split(), sorted(chans)


EXPECTED = ["36", "5", "80", "-49", "-94", "5", "2", "5", "100", "0", "14"]


def test_text_output_is_read_by_the_shape_of_the_values(tmp_path):
    (tmp_path / "sp.txt").write_text(SP_TEXT)
    first, chans = analysis(tmp_path, f'wifi_nets_from_text en0 < "{tmp_path}/sp.txt"')
    # channel 36 · 5 GHz · 80 MHz · −49/−94 dBm · Wi-Fi 5 · 2 on the same channel,
    # 5 overlapping (2 on 36, 2 on 44, 1 at 160 MHz) · emptiest: 100 with nobody.
    assert first == EXPECTED
    assert "CH 5 44 2" in chans and "CH 5 56 1" in chans and "CH 2.4 1 3" in chans


def test_json_output_gives_the_same_answer(tmp_path):
    (tmp_path / "sp.json").write_text(json.dumps(SP_JSON))
    nets = run_bash(tmp_path, f'wifi_nets_from_json "{tmp_path}/sp.json" en0')
    cur = [line for line in nets.splitlines() if line.startswith("CUR|")]
    assert cur == ["CUR|36 (5GHz, 80MHz)|-49 dBm / -94 dBm|802.11ac|173|" + WPA2 + "|<redacted>|RO"]
    first, _ = analysis(tmp_path, f'wifi_nets_from_json "{tmp_path}/sp.json" en0')
    assert first[:10] == EXPECTED[:10]


def test_own_router_is_not_counted_when_the_name_is_visible(tmp_path):
    nets = "\n".join([
        "CUR|36 (5GHz, 80MHz)|-50 dBm / -92 dBm|802.11ax|600|WPA2 Personal|Home|US",
        "OTH|36 (5GHz, 80MHz)|-50 dBm / -92 dBm|802.11a/n/ac/ax||WPA2 Personal|Home|",
        "OTH|6 (2GHz, 20MHz)|||802.11b/g/n|WPA2 Personal|Home|",
        "OTH|149 (5GHz, 80MHz)||802.11a/n/ac/ax||WPA2 Personal|Neighbour|",
    ])
    (tmp_path / "n.txt").write_text(nets + "\n")
    first, _ = analysis(tmp_path, f'cat "{tmp_path}/n.txt"', country="US")
    assert first[5:] == ["6", "0", "0", "36", "0", "1"]  # Wi-Fi 6, channel already free


def test_crowded_2_4_ghz_suggests_the_emptiest_of_1_6_11(tmp_path):
    nets = ["CUR|1 (2GHz, 20MHz)|-60 dBm / -90 dBm|802.11n|72|WPA2 Personal|<redacted>|DE"]
    nets += ["OTH|1 (2GHz, 20MHz)|||802.11b/g/n|WPA2 Personal|<redacted>|"] * 3
    nets += ["OTH|6 (2GHz, 20MHz)|||802.11b/g/n|WPA2 Personal|<redacted>|"] * 2
    nets += ["OTH|11 (2GHz, 20MHz)|||802.11b/g/n|WPA2 Personal|<redacted>|"]
    (tmp_path / "n.txt").write_text("\n".join(nets) + "\n")
    first, _ = analysis(tmp_path, f'cat "{tmp_path}/n.txt"', country="DE")
    ch, band, width, sig, noise, gen, same, share, best, best_n, nearby = first
    assert (ch, band, gen, same, share, best, best_n) == ("1", "2.4", "4", "3", "3", "11", "1")


def test_ping_jumps_and_jitter(tmp_path):
    (tmp_path / "p.txt").write_text(ping_text("192.168.1.1", PING_ROUTER))
    med, worst, jitter, jumps, loss = run_bash(tmp_path, f'wifi_ping_parse < "{tmp_path}/p.txt"').split()
    assert (med, worst, jumps, loss) == ("4", "85", "7", "0")
    assert int(jitter) >= 10
    (tmp_path / "q.txt").write_text("ping: cannot resolve 1.1.1.1\n")
    assert run_bash(tmp_path, f'wifi_ping_parse < "{tmp_path}/q.txt"').split() == ["-", "-", "-", "0", "100"]


def test_speed_and_busy_apps(tmp_path):
    (tmp_path / "nq.json").write_text(json.dumps({"dl_throughput": 352123456, "ul_throughput": 239000000,
                                                  "base_rtt": 7.5, "interface_name": "en0"}))
    assert run_bash(tmp_path, f'wifi_speed_parse "{tmp_path}/nq.json"').split() == ["352", "239"]
    (tmp_path / "a.csv").write_text(",bytes_in,bytes_out,\nGoogle Chrome H.843,67192863,2354013,\n"
                                    "Google Chrome H.900,100,100,\nTelegram.661,627253,143165,\nsyslogd.375,0,2058,\n")
    (tmp_path / "b.csv").write_text(",bytes_in,bytes_out,\nGoogle Chrome H.843,73192863,2654013,\n"
                                    "Google Chrome H.900,200,200,\nTelegram.661,627785,143841,\nsyslogd.375,0,2058,\n")
    rows = run_bash(tmp_path, f'wifi_apps_parse "{tmp_path}/a.csv" "{tmp_path}/b.csv" 5').splitlines()
    assert rows[0] == "10.08\tGoogle Chrome H"  # (6 MB + 0.3 MB) × 8 / 5 s, both Chrome processes
    assert rows[1].endswith("\tTelegram") and len(rows) == 2


def recs(tmp_path, **state):
    sets = "\n".join(f"W_{k}={v!r}" for k, v in state.items())
    return run_bash(tmp_path, f"wifi_reset\n{sets}\n: > \"$MACUP_TMP/wifi.apps\"\nwifi_recommendations\nprintf '%s' \"$REC\"")


def test_recommendations_for_the_slow_wifi_above(tmp_path):
    out = recs(tmp_path, CH="36", BAND="5", WIDTH="80", SIGNAL="-49", GEN="5", PHY="802.11ac", SHARE="5",
               SAME="2", BEST="100", BEST_N="0", R_SPIKES="7", R_JIT="19", AIRDROP="everyone",
               HANDOFF="on", AIRPLAY="on", AWDL="1", DL="350", PLAN="1000")
    lines = out.strip().splitlines()
    assert lines[0].startswith("warn|Turn off AirDrop, Handoff and AirPlay Receiver|")
    assert lines[1].startswith("warn|On your router: move Wi-Fi to channel 100 (80 MHz)|5 nearby networks share your channel 36.")
    assert "radar" in lines[1]
    assert lines[2].startswith("info|Wi-Fi 5 router")
    assert len(lines) == 3


def test_healthy_wifi_gets_no_fixes(tmp_path):
    out = recs(tmp_path, CH="149", BAND="5", WIDTH="80", SIGNAL="-52", GEN="6", PHY="802.11ax", SHARE="0",
               BEST="149", R_SPIKES="0", R_JIT="1", AIRDROP="contacts", HANDOFF="on", AIRPLAY="on", AWDL="0")
    assert out.strip().splitlines() == ["ok|Your Wi-Fi looks healthy|Good signal, steady ping and a free channel. Run macup wifi again if it feels slow.|"]


def test_whole_screen_with_recorded_mac_output(tmp_path):
    (tmp_path / "sp.txt").write_text(SP_TEXT)
    (tmp_path / "sp.json").write_text(json.dumps(SP_JSON))
    (tmp_path / "router.txt").write_text(ping_text("192.168.1.1", PING_ROUTER))
    (tmp_path / "net.txt").write_text(ping_text("1.1.1.1", PING_CALM))
    (tmp_path / "speed.json").write_text(json.dumps({"dl_throughput": 350400000, "ul_throughput": 239000000}))
    body = f'''
networksetup() {{ printf 'Hardware Port: Thunderbolt Bridge\\nDevice: bridge0\\n\\nHardware Port: Wi-Fi\\nDevice: en0\\n'; }}
ipconfig() {{ case "$1" in getifaddr) echo 192.168.1.5 ;; getoption) echo 192.168.1.1 ;; esac; }}
system_profiler() {{ if [ "$1" = "-json" ]; then cat "{tmp_path}/sp.json"; else cat "{tmp_path}/sp.txt"; fi; }}
ping() {{ local host; for host; do :; done; if [ "$host" = 1.1.1.1 ]; then cat "{tmp_path}/net.txt"; else cat "{tmp_path}/router.txt"; fi; }}
networkQuality() {{ cat "{tmp_path}/speed.json"; }}
nettop() {{ printf ',bytes_in,bytes_out,\\nTelegram.661,%s,100,\\n' "$(( $(date +%s%N) % 1000 ))"; }}
scutil() {{ case "$1" in --dns) printf 'DNS configuration\\n\\nresolver #1\\n  nameserver[0] : 1.1.1.1\\n  nameserver[1] : 8.8.8.8\\nresolver #2\\n';; --nc) echo 'Available network connection services';; --proxy) echo '<dictionary> {{ }}';; esac; }}
pmset() {{ printf ' powermode            0\\n'; }}
defaults() {{ case "$*" in *DiscoverableMode*) echo Everyone ;; *ActivityAdvertisingAllowed*) echo 1 ;; *Airplay*) echo 1 ;; *) return 1 ;; esac; }}
ifconfig() {{ printf 'awdl0: flags=8863<UP>\\n\\tstatus: active\\n'; }}
sleep() {{ :; }}
W_PLAN=1000
cmd_wifi
'''
    out = run_bash(tmp_path, body)
    for text in ["7  Wi-Fi Check", "350 Mbps", "35% of your 1000 Mbps", "4 ms · worst 85 ms",
                 "5 GHz · channel 36 · 80 MHz", "Wi-Fi 5 (802.11ac)", "-49 dBm · excellent (noise -94 dBm)",
                 "5 nearby networks use your channel", "Emptiest channel: 100 (0 networks)",
                 "1.1.1.1, 8.8.8.8", "Everyone", "Turn off AirDrop, Handoff and AirPlay Receiver",
                 "move Wi-Fi to channel 100 (80 MHz)"]:
        assert text in out, text
    # Not an interactive Terminal: nothing is changed and nothing is saved.
    assert not (tmp_path / "state").exists()


def test_undo_shows_the_saved_settings(tmp_path):
    out = run_bash(tmp_path, 'cmd_wifi_undo')
    assert "Nothing saved yet" in out
    body = '''wifi_reset; W_AIRDROP=everyone; W_HANDOFF=on; W_AIRPLAY=off; W_CH=36; W_BAND=5; W_WIDTH=80
W_ROUTER=192.168.1.1; W_DL=350; W_R_MED=4; W_R_MAX=85; W_R_JIT=19
wifi_write_before; cmd_wifi_undo'''
    out = run_bash(tmp_path, body)
    for text in ["AirDrop: Everyone", "Handoff: On", "AirPlay Receiver: Off", "Wi-Fi channel: 5 GHz · channel 36 · 80 MHz",
                 "Router page: http://192.168.1.1", "Download: 350 Mbps"]:
        assert text in out, text


def test_never_writes_settings_by_itself():
    code = "\n".join(line.split("#", 1)[0] for line in (ROOT / "lib" / "wifi.sh").read_text().splitlines())
    assert "defaults write" not in code and "defaults -currentHost write" not in code
    assert "networksetup -set" not in code and "killall" not in code and "sudo" not in code


TPLINK_PAGE = ("HTTP/1.1 200 OK\r\nServer: lighttpd\r\n\r\n<html><head><title>Opening...</title>"
               "<script src=\"/js/tplink.js\"></script></head><body></body></html>")
ZTE_PAGE = ("HTTP/1.1 200 OK\r\n\r\n<html><head><title>F618</title></head>"
            "<body>©2008-2020 ZTE Corporation. All rights reserved.</body></html>")


def test_routers_are_named_and_the_second_router_is_suggested(tmp_path):
    (tmp_path / "tplink.html").write_text(TPLINK_PAGE)
    (tmp_path / "zte.html").write_text(ZTE_PAGE)
    body = f'''
ping() {{ :; }}
ipconfig() {{ echo 255.255.255.0; }}
arp() {{ printf '? (192.168.1.1) at 24:58:6e:d7:c8:d1 on en0 ifscope [ethernet]\\n? (192.168.1.5) at e:4a:6d:b8:ee:c on en0 ifscope permanent [ethernet]\\n? (192.168.1.8) at 98:da:c4:b8:e:8e on en0 ifscope [ethernet]\\n? (192.168.1.9) at 86:1e:f6:66:12:7 on en0 ifscope [ethernet]\\n? (192.168.1.255) at ff:ff:ff:ff:ff:ff on en0 ifscope [ethernet]\\n'; }}
curl() {{ local u; for u; do :; done; case "$u" in http://192.168.1.1/) cat "{tmp_path}/zte.html" ;; http://192.168.1.8/) cat "{tmp_path}/tplink.html" ;; *) return 7 ;; esac; }}
wifi_reset; W_DEV=en0; W_IP=192.168.1.5; W_ROUTER=192.168.1.1
wifi_pick_router
echo "PICK=$REPLY"
cat "$MACUP_TMP/wifi.routers"
'''
    out = run_bash(tmp_path, body)
    assert "192.168.1.1" in out and "ZTE · F618 · main router" in out
    assert "TP-Link · Opening..." in out
    assert "PICK=192.168.1.8" in out          # the TP-Link behind the provider's box
    assert "192.168.1.9" not in out.split("PICK=")[1]  # a phone has no web page


def test_verdict_says_if_the_speed_went_up(tmp_path):
    out = run_bash(tmp_path, '''wifi_verdict_line 470 560; wifi_verdict_line 470 480; wifi_verdict_line 470 400''')
    assert out.splitlines() == ["ok\tFaster: 470 → 560 Mbps (+19%)", "info\tAbout the same: 470 → 480 Mbps",
                                "warn\tSlower: 470 → 400 Mbps (-15%)"]
    body = '''wifi_reset; W_DL=480; W_R_MAX=20; W_R_JIT=3; W_GEN=5
wifi_before_after 470 85 17'''
    out = run_bash(tmp_path, body)
    assert "≈  About the same: 470 → 480 Mbps" in out
    assert "✓  Steadier: worst ping 85 → 20 ms" in out
    assert "router’s limit" in out


def test_each_check_is_compared_with_the_last_one(tmp_path):
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "wifi-last.txt").write_text("date=2026-11-21 21:40\ndl=470\nrmax=85\nrjit=17\nchannel=36\n")
    body = '''wifi_reset; wifi_read_last; W_DL=560; W_UL=240; W_R_MED=4; W_R_MAX=9; W_R_JIT=1; W_I_MED=6; W_I_MAX=8; W_I_JIT=1
wifi_show_speed'''
    out = run_bash(tmp_path, body)
    assert "Since your last check" in out and "Faster: 470 → 560 Mbps (+19%)" in out and "2026-11-21 21:40" in out


def test_unreadable_setting_says_where_to_look(tmp_path):
    out = run_bash(tmp_path, '''wifi_reset; W_AIRDROP=everyone; W_HANDOFF=off; W_AIRPLAY=""; wifi_show_mac''')
    assert "AirPlay Receiver             check in System Settings" in out
    assert "·  AirPlay Receiver" in out
