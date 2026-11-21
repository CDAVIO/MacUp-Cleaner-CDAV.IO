#!/usr/bin/env python3
"""Writes docs/images/macup-start.gif — a 5-second visual tutorial for the README:
open Terminal, paste the install line, type macup, pick a number.

    pip install pillow
    python3 docs/images/src/start_gif.py

The menu texts come from lib/lang/en.sh, so the GIF shows what MacUp prints.
Drawing helpers are shared with wifi_gif.py.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wifi_gif as g  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

ROOT = g.ROOT
OUT = ROOT / "docs" / "images" / "macup-start.gif"
S = dict(re.findall(r"^S_([a-z_0-9]+)='(.*)'$", (ROOT / "lib/lang/en.sh").read_text(), re.M))
INSTALL = "curl -fsSL https://raw.githubusercontent.com/CDAVIO/MacUp-Cleaner-CDAV.IO/main/install.sh | bash"
SMALL = g.font(g.FONTS, 12)
Y, D, M, W = g.Y, g.D, g.M, g.W


def macup_icon(size=40):
    """MacUp’s own logo (site/favicon.svg): a big white ✦, a small yellow one and a smile."""
    s = size * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([s * .03, s * .03, s * .97, s * .97], radius=s * .22, fill="#262626")
    r = s * .3
    d.arc([s * .5 - r, s * .63 - r * 1.25, s * .5 + r, s * .63], 20, 160, fill=(255, 255, 255, 90), width=round(s * .053))
    g.sparkle(d, s * .48, s * .42, s * .2, W, waist=.22)
    g.sparkle(d, s * .72, s * .24, s * .07, Y, waist=.22)
    return im.resize((size, size), Image.LANCZOS)


LOGO = macup_icon()


def step_badge(im, n, text, x=g.PAD, y=None):
    """Yellow step number + caption in the bottom-left corner."""
    d = ImageDraw.Draw(im)
    y = y or g.HEIGHT - 46
    d.ellipse([x, y, x + 26, y + 26], fill=Y)
    d.text((x + 13 - g.FB.getlength(str(n)) / 2, y + 4), str(n), font=g.FB, fill="#0a0a0a")
    d.text((x + 36, y + 4), text, font=g.F, fill=M)


def frame(lines, step, caption, cursor=False, small_row=None):
    im = g.frame([], False, title="Terminal", pill=None, logo=LOGO)
    d = ImageDraw.Draw(im)
    for row, parts in enumerate(lines):
        x = g.PAD
        fnt, cw = (SMALL, SMALL.getlength("M")) if row == small_row else (None, g.CW)
        for text, color, bold in parts:
            f = fnt or (g.FB if bold else g.F)
            d.text((x, g.TOP + row * g.LH + (2 if fnt else 0)), text, font=f, fill=color)
            x += cw * len(text)
        if cursor and row == len(lines) - 1:
            d.rectangle([x + 2, g.TOP + row * g.LH + 2, x + cw, g.TOP + row * g.LH + g.LH - 4], fill=Y)
    step_badge(im, step, caption)
    return im


def build():
    frames, durations = [], []

    def add(*args, ms, **kw):
        frames.append(frame(*args, **kw))
        durations.append(ms)

    # 1 · Open Terminal (0–800 ms)
    add([], 1, "Open Terminal:  ⌘ Space  →  type “Terminal”  →  Enter", ms=800, cursor=False)
    # 2 · Paste the install line (800–2000 ms)
    prompt = [("$ ", Y, True)]
    add([prompt + [(INSTALL[:40], M, False)]], 2, "Paste the install line (one time)", ms=250, cursor=True, small_row=0)
    add([prompt + [(INSTALL, M, False)]], 2, "Paste the install line (one time)", ms=350, small_row=0)
    done = [[("✓ ", W, True), ("MacUp installed · type ", M, False), ("macup", Y, True)]]
    add([prompt + [(INSTALL, M, False)], *done], 2, "Paste the install line (one time)", ms=600, small_row=0)
    # 3 · Type macup and pick a number (2000–5000 ms)
    base = [prompt + [(INSTALL, M, False)], *done, []]
    for n in (2, 4):
        add(base + [prompt + [("macup"[:n + 1], M, False)]], 3, "Type macup — then pick a number", ms=100, cursor=True, small_row=0)
    menu = [[("  ✦ ", Y, False), ("MacUp", W, True), ("  " + S["tagline"], D, False)], [("  " + "─" * 62, D, False)]]
    items = [("1", "clean_title"), ("2", "mac_title"), ("3", "protection_title"), ("4", "performance_title"),
             ("5", "check_title"), ("6", "recent_title"), ("7", "wifi_title")]
    shown = base[:2] + [prompt + [("macup", M, False)]]
    add(shown + menu, 3, "Type macup — then pick a number", ms=250, small_row=0)
    for k in range(1, len(items) + 1):
        rows = [[(f"  {n}  ", Y, False), (S[key], W if n == "7" else M, n == "7")] for n, key in items[:k]]
        add(shown + menu + rows, 3, "Type macup — then pick a number", ms=90, small_row=0)
    rows = [[(f"  {n}  ", Y, False), (S[key], W if n == "7" else M, n == "7")] for n, key in items]
    ask = [[], [("  › ", Y, False), (S["choose"] + " ", M, False)]]
    add(shown + menu + rows + ask, 3, "Type macup — then pick a number", ms=500, cursor=True, small_row=0)
    ask7 = [[], [("  › ", Y, False), (S["choose"] + " ", M, False), ("7", Y, True)]]
    add(shown + menu + rows + ask7, 3, "Type macup — then pick a number  ·  7 = Wi-Fi Check", ms=5000 - sum(durations) - 0,
        small_row=0)
    assert sum(durations) == 5000, sum(durations)
    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=128) for f in frames]
    pal[0].save(OUT, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=True, disposal=1)
    print(f"wrote {OUT.relative_to(ROOT)} · {len(frames)} frames · {sum(durations) / 1000:.1f} s · {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    build()
