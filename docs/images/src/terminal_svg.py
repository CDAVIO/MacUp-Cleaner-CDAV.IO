#!/usr/bin/env python3
"""Writes docs/images/terminal.svg — an animated Terminal for the README.

    python3 docs/images/src/terminal_svg.py

Texts come from lib/lang/en.sh, so the animation shows exactly what MacUp
prints. Values are examples (not anyone's real Mac). Pure SVG + CSS, no
scripts, so GitHub shows it as an image and it loops by itself.
"""
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
S = dict(re.findall(r"^S_([a-z_0-9]+)='(.*)'$", (ROOT / "lib/lang/en.sh").read_text(), re.M))


def t(key, *args):
    text = S[key]
    for i, a in enumerate(args, 1):
        text = text.replace("{%d}" % i, str(a))
    return text


W, LH, X0, Y0 = 860, 21, 26, 76
LOOP = 22.0  # seconds
Y, D, M = "#ffd905", "#8d8e92", "#e8e8e6"

# Each scene: (start, end) seconds and its lines: (appear_at, [(text, color, bold)], typed)
bar = lambda p, n=24: ("█" * round(p * n / 100), "░" * (n - round(p * n / 100)))  # noqa: E731


def wrap(text, width=96):
    """Two lines, split at a space, like the Terminal wraps a long sentence."""
    if len(text) <= width:
        return [text, ""]
    cut = text.rfind(" ", 0, width)
    return [text[:cut], text[cut + 1:]]


def row(icon, ic, label, value, note=""):
    parts = [(f"  {icon}  ", ic, False), (f"{label:<29}", M, False), (value, M, False)]
    if note:
        parts.append((f"  · {note}", D, False))
    return parts


menu = [
    (0.0, [("$ ", Y, True), ("macup", M, False)], True),
    (1.4, [], False),
    (1.5, [("  ✦ ", Y, False), ("MacUp", "#ffffff", True), ("  " + t("tagline"), D, False)], False),
    (1.6, [("  " + "─" * 62, D, False)], False),
]
items = [("1", "clean_title", "menu_clean"), ("2", "mac_title", "menu_mac"), ("3", "protection_title", "menu_protect"),
         ("4", "performance_title", "menu_perf"), ("5", "check_title", "menu_check"), ("6", "recent_title", "menu_recent")]
tm = 1.75
for n, title, desc in items:
    menu.append((tm, [(f"  {n}  ", Y, False), (t(title), "#ffffff", True)], False))
    menu.append((tm, [("     " + t(desc), D, False)], False))
    tm += 0.18
menu.append((tm, [("  q  " + t("quit"), D, False)], False))
menu += [(tm + 0.1, [], False), (tm + 0.2, [("  › ", Y, False), (t("choose") + " ", M, False), ("5", Y, True)], False)]

b = bar(93)
check = [
    (0.0, [("  5  ", Y, False), (t("check_title"), "#ffffff", True)], False),
    (0.1, [("  " + "─" * 62, D, False)], False),
    (0.2, [("  " + wrap(t("check_intro"))[0], D, False)], False),
    (0.2, [("  " + wrap(t("check_intro"))[1], D, False)], False),
    (0.3, [], False),
    (0.35, [("  ⠋ ", Y, False), (t("checking"), M, False), ("  " + t("part_storage") + " · " + t("part_battery") + " · …", D, False)], False, 2.4),
    (2.4, [("  " + t("battery_health") + "  ", "#ffffff", True), (b[0], Y, False), (b[1], "#3a3a3a", False),
           ("  93%", Y, True), ("  " + t("k_cycles") + ": 228", D, False)], False),
    (2.6, [], False),
    (2.8, row("!", Y, t("part_storage"), t("note_storage", "59.1 GB", 11), t("grade_attention")), False),
    (3.0, row("✓", Y, t("part_ssd"), "S.M.A.R.T.: Verified", t("grade_good")), False),
    (3.2, row("✓", Y, t("part_battery"), f'{t("k_bat_health")} 93% · {t("k_cycles")}: 228', t("grade_good")), False),
    (3.4, row("✓", Y, t("part_memory"), t("note_memory", 39, 0), t("grade_good")), False),
    (3.6, row("✓", Y, t("part_cpu"), t("note_cpu", 18, 2), t("grade_good")), False),
    (3.8, row("✓", Y, t("part_protection"), t("note_protection", 7, 7), t("grade_good")), False),
    (4.0, row("!", Y, t("part_cleanup"), "3.1 GB", t("grade_attention")), False),
    (4.3, [], False),
    (4.5, [("  →  ", Y, False), (t("report_recs"), "#ffffff", True)], False),
    (4.8, [("  ✕  ", Y, False), (t("rec_space_low", 11), "#ffffff", True)], False),
    (5.0, [("     $ macup clean", Y, False)], False),
    (5.6, [], False),
    (5.8, [("  ✓ ", Y, False), (t("pdf_saved"), M, True)], False),
    (6.0, [("     ~/Downloads/MacUp-Health-Report-2026-11-01-1720.pdf", Y, False)], False),
]

SCENES = [(0.0, 7.8, menu), (8.0, 21.6, check)]
H = Y0 + LH * max(len(s[2]) for s in SCENES) + 26


def pct(sec):
    return f"{max(0.0, min(100.0, sec / LOOP * 100)):.3f}%"


css, body = [], []
uid = 0
for s_start, s_end, lines in SCENES:
    for i, line in enumerate(lines):
        at, parts, typed = line[:3]
        until = s_start + line[3] if len(line) > 3 else s_end
        if not parts or not any(txt.strip() for txt, _, _ in parts):
            continue
        uid += 1
        show = s_start + at
        y = Y0 + i * LH
        name = f"l{uid}"
        # visible from `show` until the scene ends, every loop
        css.append(
            f"@keyframes {name}{{0%,{pct(show - 0.001)}{{opacity:0}}{pct(show)},{pct(until)}{{opacity:1}}"
            f"{pct(until + 0.001)},100%{{opacity:0}}}}.{name}{{animation:{name} {LOOP}s steps(1,end) infinite}}"
        )
        tspans = "".join(
            f'<tspan fill="{c}"{" font-weight=\"700\"" if bold else ""}>{html.escape(txt)}</tspan>'
            for txt, c, bold in parts
        )
        if typed:
            # typing: a clip rectangle grows over 1.1 s
            css.append(
                f"@keyframes w{uid}{{0%,{pct(show)}{{width:0}}{pct(show + 1.1)},{pct(s_end)}{{width:{W}px}}"
                f"{pct(s_end + 0.001)},100%{{width:0}}}}.w{uid}{{animation:w{uid} {LOOP}s linear infinite}}"
            )
            body.append(f'<clipPath id="c{uid}"><rect class="w{uid}" x="0" y="{y - 16}" height="22" width="0"/></clipPath>')
            body.append(f'<text x="{X0}" y="{y}" clip-path="url(#c{uid})">{tspans}</text>')
        else:
            body.append(f'<text class="{name}" x="{X0}" y="{y}" opacity="0">{tspans}</text>')

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="MacUp running in Terminal: menu, then the complete check with battery health and a PDF report">
<style>
text{{font-family:"SF Mono",SFMono-Regular,Menlo,Monaco,Consolas,"DejaVu Sans Mono",monospace;font-size:13.5px;white-space:pre}}
{"".join(css)}
@media (prefers-reduced-motion: reduce){{*{{animation:none!important}}text{{opacity:1}}}}
</style>
<rect width="{W}" height="{H}" rx="14" fill="#0d0d0d"/>
<rect width="{W}" height="40" rx="14" fill="#1b1b1b"/><rect y="26" width="{W}" height="14" fill="#1b1b1b"/>
<circle cx="24" cy="20" r="6.5" fill="#ff5f57"/><circle cx="46" cy="20" r="6.5" fill="#febc2e"/><circle cx="68" cy="20" r="6.5" fill="#28c840"/>
<text x="{W / 2}" y="25" text-anchor="middle" fill="#8a8a8a" style="font-family:-apple-system,Segoe UI,Helvetica,sans-serif;font-size:13px;font-weight:600">Terminal — macup</text>
{"".join(body)}
</svg>
'''
out = ROOT / "docs/images/terminal.svg"
out.write_text(svg)
print(f"wrote {out.relative_to(ROOT)} ({len(svg) // 1024} KB, {W}x{H})")
