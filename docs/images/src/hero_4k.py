#!/usr/bin/env python3
"""Writes docs/images/macup-4k.png — the 3840×2160 MacUp hero image for the README.

    python3 docs/images/src/hero_4k.py          # needs rsvg-convert (librsvg)

Fonts: Poppins and JetBrains Mono (both SIL Open Font License); any sans /
monospace font works, the shapes stay the same. Menu texts come from
lib/lang/en.sh. The SVG source is written next to this script.
"""
import html
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SVG = Path(__file__).with_name("macup-4k.svg")
PNG = ROOT / "docs" / "images" / "macup-4k.png"
S = dict(re.findall(r"^S_([a-z_0-9]+)='(.*)'$", (ROOT / "lib/lang/en.sh").read_text(), re.M))
Y, D, M, W = "#ffd905", "#8d8e92", "#e8e8e6", "#ffffff"
SANS, MONO = "Poppins, 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif", "'JetBrains Mono', Menlo, 'DejaVu Sans Mono', monospace"
e = html.escape


def text(x, y, s, size, fill, weight=500, family=SANS, spacing=0, anchor="start"):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'letter-spacing="{spacing}" fill="{fill}" text-anchor="{anchor}">{s}</text>')


def chip(x, y, label, size=40):
    w = int(len(label) * size * 0.6) + 130
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{size * 2}" rx="{size}" fill="#121212" stroke="#2e2e2e" stroke-width="3"/>'
            f'<circle cx="{x + 52}" cy="{y + size}" r="11" fill="{Y}"/>'
            + text(x + 82, y + size * 1.36, e(label), size, "#d4d4d4", 600)), w


def logo(x, y, s):
    """MacUp's ✦ logo (same shapes as site/favicon.svg, drawn at size s)."""
    k = s / 64
    return f'''<g transform="translate({x} {y}) scale({k})">
  <rect x="2" y="2" width="60" height="60" rx="14" fill="url(#tile)"/>
  <path d="M15.6 40.5a19 19 0 0 0 32.8 0" stroke="#fff" stroke-opacity=".35" stroke-width="3.4" fill="none" stroke-linecap="round"/>
  <path d="M29.5 12.5c.7 7.3 1.9 8.6 9.3 9.4-7.4.8-8.6 2-9.3 9.4-.8-7.4-2-8.6-9.4-9.4 7.4-.8 8.6-2.1 9.4-9.4Z" fill="#fff" transform="translate(1.5 5) scale(1.05)"/>
  <path d="M46 12c.3 2.6.7 3.1 3.3 3.4-2.6.3-3 .7-3.3 3.3-.3-2.6-.8-3-3.4-3.3 2.6-.3 3.1-.8 3.4-3.4Z" fill="{Y}"/>
</g>'''


def terminal(x, y, w):
    fs, lh, pad = 46, 84, 70
    items = [("1", "clean_title", "caches → Trash"), ("2", "mac_title", "SSD · battery · memory"),
             ("3", "protection_title", "built-in security"), ("4", "performance_title", "load · busy apps"),
             ("5", "check_title", "+ PDF report"), ("6", "recent_title", "clear the list"),
             ("7", "wifi_title", "speed · ping · channel")]
    rows = 4 + len(items) + 2
    h = 110 + pad + rows * lh
    out = [f'<rect x="{x}" y="{y + 40}" width="{w}" height="{h}" rx="48" fill="#000" opacity=".55" filter="url(#blur)"/>',
           f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="48" fill="#141414" stroke="#ffffff" stroke-opacity=".1" stroke-width="3"/>',
           f'<path d="M{x} {y + 110}V{y + 48}a48 48 0 0 1 48-48H{x + w - 48}a48 48 0 0 1 48 48V{y + 110}Z" fill="#1d1d1d"/>']
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        out.append(f'<circle cx="{x + 60 + i * 52}" cy="{y + 55}" r="16" fill="{c}"/>')
    out.append(text(x + w / 2, y + 72, "Terminal", 40, D, 500, SANS, 0, "middle"))
    cx, cy = x + pad, y + 110 + pad + 40
    mono = lambda xx, yy, s, fill, wt=400: text(xx, yy, s, fs, fill, wt, MONO)  # noqa: E731
    cw = fs * 0.6
    out.append(mono(cx, cy, "$", Y, 700) + mono(cx + 2 * cw, cy, "macup", M))
    cy += lh * 1.4
    out.append(mono(cx, cy, "✦", Y) + mono(cx + 2 * cw, cy, "MacUp", W, 700))
    cy += lh * 0.6
    out.append(f'<line x1="{cx}" y1="{cy}" x2="{x + w - pad}" y2="{cy}" stroke="{D}" stroke-opacity=".5" stroke-width="3"/>')
    cy += lh
    for n, key, note in items:
        if n == "7":
            out.append(f'<rect x="{cx - 24}" y="{cy - lh * 0.68}" width="{w - 2 * pad + 48}" height="{lh * 0.96}" rx="18" fill="{Y}" fill-opacity=".12" stroke="{Y}" stroke-opacity=".45" stroke-width="3"/>')
        out.append(mono(cx, cy, n, Y) + mono(cx + 3 * cw, cy, e(S[key]), W if n == "7" else M, 700 if n == "7" else 400)
                   + mono(cx + 23 * cw, cy, e(note), D))
        cy += lh
    cy += lh * 0.4
    out.append(mono(cx, cy, "›", Y) + mono(cx + 2 * cw, cy, e(S["choose"]), M) + mono(cx + (3 + len(S["choose"])) * cw, cy, "7", Y, 700))
    out.append(f'<rect x="{cx + (4 + len(S["choose"])) * cw + 6}" y="{cy - fs * 0.8}" width="{cw}" height="{fs}" fill="{Y}"/>')
    return "\n".join(out)


def build():
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="3840" height="2160" viewBox="0 0 3840 2160">
<defs>
  <radialGradient id="glow" cx="3260" cy="260" r="1750" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="{Y}" stop-opacity=".30"/><stop offset=".45" stop-color="{Y}" stop-opacity=".08"/><stop offset="1" stop-color="{Y}" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="glow2" cx="300" cy="2200" r="1300" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#ffffff" stop-opacity=".06"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="tile" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#333"/><stop offset="1" stop-color="#0a0a0a"/></linearGradient>
  <filter id="blur" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="40"/></filter>
</defs>
<rect width="3840" height="2160" fill="#0a0a0a"/>
<rect width="3840" height="2160" fill="url(#glow)"/>
<rect width="3840" height="2160" fill="url(#glow2)"/>''']
    L = 260
    parts.append(logo(L, 250, 210))
    parts.append(text(L + 250, 405, "MacUp", 150, W, 800, SANS, -3))
    parts.append(text(L, 790, "Your Mac’s health,", 168, W, 800, SANS, -5))
    parts.append(text(L, 990, "right in <tspan fill='" + Y + "'>Terminal.</tspan>", 168, W, 800, SANS, -5))
    parts.append(text(L, 1160, "Clean hidden caches, check SSD, battery and security,", 58, "#a3a4a8", 500))
    parts.append(text(L, 1245, "and find out why your Wi-Fi is slow.", 58, "#a3a4a8", 500))
    x = L
    for label in ("Free forever", "Open source", "No account", "No admin password"):
        svg, w = chip(x, 1350, label)
        parts.append(svg)
        x += w + 28
    parts.append(f'<line x1="{L}" y1="1830" x2="{3840 - L}" y2="1830" stroke="#ffffff" stroke-opacity=".08" stroke-width="3"/>')
    parts.append(text(L, 1945, "Works on every Mac", 46, W, 600)
                 + text(L + 520, 1945, "MacBook · iMac · Mac mini · Mac Studio · Mac Pro   ·   Intel and Apple silicon (M1 and later)   ·   macOS 13 or newer   ·   7 languages", 46, D, 500))
    parts.append(terminal(2160, 300, 1420))
    parts.append("</svg>\n")
    SVG.write_text("\n".join(parts))
    subprocess.run(["rsvg-convert", "-w", "3840", "-h", "2160", str(SVG), "-o", str(PNG)], check=True)
    print(f"wrote {PNG.relative_to(ROOT)} · 3840×2160 · {PNG.stat().st_size // 1024} KB")


if __name__ == "__main__":
    build()
