#!/usr/bin/env python3
"""Writes docs/images/wifi-check.gif — the 3-second Wi-Fi Check animation for the README.

    pip install pillow
    python3 docs/images/src/wifi_gif.py

Values are examples (350 → 600 Mbps), not anyone's real Wi-Fi. The texts
match what `macup wifi` prints in English (lib/lang/en.sh).
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "images" / "wifi-check.gif"

BG, TERM, BAR = "#0a0a0a", "#141414", "#1d1d1d"
Y, D, M, W, TRACK = "#ffd905", "#8d8e92", "#e8e8e6", "#ffffff", "#3a3a3a"
WIDTH, HEIGHT, PAD, TOP, LH, SIZE = 860, 452, 26, 62, 22, 15

FONTS = ["/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/SFNSMono.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "DejaVuSansMono.ttf"]
BOLD = ["/System/Library/Fonts/Menlo.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "DejaVuSansMono-Bold.ttf"]


def font(paths, size, index=0):
    for p in paths:
        try:
            return ImageFont.truetype(p, size, index=index)
        except OSError:
            continue
    raise SystemExit("No monospace font found (install DejaVu Sans Mono).")


F = font(FONTS, SIZE)
FB = font(BOLD, SIZE, index=1 if BOLD[0].endswith(".ttc") and Path(BOLD[0]).exists() else 0)
CW = F.getlength("M")  # one column


def bar(pct, n=20):
    on = round(pct * n / 100)
    return "█" * on, "░" * (n - on)


def sparkle(d, x, y, r, fill, waist=.28):
    pts = []
    for i in range(8):
        a = math.pi / 4 * i - math.pi / 2
        rad = r if i % 2 == 0 else r * waist
        pts.append((x + rad * math.cos(a), y + rad * math.sin(a)))
    d.polygon(pts, fill=fill)


def icon(size=40):
    """The Wi-Fi Check logo: Wi-Fi arcs, a yellow up-arrow and MacUp's ✦ (drawn at 4× then scaled)."""
    s = size * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([s * .03, s * .03, s * .97, s * .97], radius=s * .22, fill="#262626")
    cx, cy, w = s / 2, s * .71, max(2, round(s * .056))
    for r, alpha in ((.375, 90), (.266, 166), (.156, 255)):
        rr = r * s
        d.arc([cx - rr, cy - rr, cx + rr, cy + rr], 225, 315, fill=(255, 255, 255, alpha), width=w)
    d.line([cx, s * .84, cx, s * .70], fill=Y, width=w)
    d.line([cx - s * .072, s * .74, cx, s * .665, cx + s * .072, s * .74], fill=Y, width=w, joint="curve")
    sparkle(d, s * .77, s * .23, s * .085, Y)  # ✦
    return im.resize((size, size), Image.LANCZOS)


ICON = icon()


def frame(lines, cursor=False, title="macup wifi", pill="Example values", logo=None):
    im = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([10, 10, WIDTH - 10, HEIGHT - 10], radius=14, fill=TERM, outline="#2a2a2a")
    d.rounded_rectangle([10, 10, WIDTH - 10, 44], radius=14, fill=BAR)
    d.rectangle([10, 30, WIDTH - 10, 44], fill=BAR)
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        d.ellipse([26 + i * 20, 21, 38 + i * 20, 33], fill=c)
    d.text(((WIDTH - F.getlength(title)) / 2, 18), title, font=F, fill=D)
    logo = logo or ICON
    im.paste(logo, (WIDTH - PAD - 46, 54), logo)
    for row, parts in enumerate(lines):
        x = PAD
        for text, color, bold in parts:
            d.text((x, TOP + row * LH), text, font=FB if bold else F, fill=color)
            x += CW * len(text)
        if cursor and row == len(lines) - 1:
            d.rectangle([x + 2, TOP + row * LH + 2, x + CW, TOP + row * LH + LH - 4], fill=Y)
    if pill:
        pw = F.getlength(pill) + 20
        d.rounded_rectangle([WIDTH - PAD - pw, HEIGHT - 44, WIDTH - PAD, HEIGHT - 20], radius=12, outline="#3a3a3a")
        d.text((WIDTH - PAD - pw + 10, HEIGHT - 40), pill, font=F, fill=D)
    return im


def row(mark, mc, label, value, note=""):
    parts = [(f"  {mark}  ", mc, False), (f"{label:<19}", M, False), (value, M, False)]
    if note:
        parts.append((note, D, False))
    return parts


CMD = "macup wifi"
HEAD = [[], [("  ✦ ", Y, False), ("MacUp", W, True), ("  Wi-Fi Check", D, False)], [("  " + "─" * 62, D, False)]]
on, off = bar(35)
BEFORE = [
    [("  !  ", Y, False), (f"{'Download':<19}", M, False), ("350 Mbps  ", W, True), (on, Y, False),
     (off, TRACK, False), ("  35% of your 1000 Mbps", D, False)],
    row("!", Y, "Ping to router", "4 ms · worst 258 ms · jitter 47 ms"),
    row("!", Y, "Shared channel", "5 nearby networks use channel 36"),
]
FIX = [
    [],
    [("  →  ", Y, False), ("Fix", W, True)],
    row("✓", W, "AirDrop & Handoff", "AirDrop → No One · Handoff off · AirPlay off"),
    row("✓", W, "Router channel", "36 → 100", "  (nobody else there)"),
]


def after(dl, done):
    up = f"  ▲ +{round((dl - 350) * 100 / 350)}%" if done else ""
    return [
        [],
        [(" " * 24, M, False), (f"{'Before':<12}", D, False), ("After", D, False)],
        [(f"     {'Download':<19}", M, False), (f"{'350 Mbps':<12}", M, False), (f"{dl} Mbps", W, True), (up, Y, True)],
        [(f"     {'Worst ping':<19}", M, False), (f"{'258 ms':<12}", M, False), ("40 ms" if done else "", W, True)],
    ]


def build():
    frames, durations = [], []

    def add(lines, ms, cursor=False):
        frames.append(frame(lines, cursor))
        durations.append(ms)

    for n in range(0, len(CMD) + 1, 2):  # typing: 0–450 ms
        add([[("$ ", Y, True), (CMD[:n], M, False)]], 75, cursor=True)
    prompt = [[("$ ", Y, True), (CMD, M, False)]]
    add(prompt + HEAD, 250)                                          # 450–700
    for i in range(1, 4):                                            # 700–1150
        add(prompt + HEAD + BEFORE[:i], 150)
    add(prompt + HEAD + BEFORE + FIX[:2], 150)                       # 1150–1650
    add(prompt + HEAD + BEFORE + FIX[:3], 175)
    add(prompt + HEAD + BEFORE + FIX, 175)
    for dl in (350, 400, 450, 500, 550, 600):                        # 1650–2300
        add(prompt + HEAD + BEFORE + FIX + after(dl, False), 650 // 6 if dl < 600 else 650 - 5 * (650 // 6))
    add(prompt + HEAD + BEFORE + FIX + after(600, True), 700)        # 2300–3000
    assert sum(durations) == 3000, sum(durations)
    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=128) for f in frames]
    pal[0].save(OUT, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True, disposal=1)
    print(f"wrote {OUT.relative_to(ROOT)} · {len(frames)} frames · {sum(durations) / 1000:.1f} s · {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    build()
