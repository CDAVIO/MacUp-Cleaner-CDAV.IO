#!/usr/bin/env python3
"""Builds the MacUp website into site/.

    python3 site-src/build.py

Inputs:  site-src/template.html, site-src/strings/<lang>.json (website texts),
         lib/lang/<lang>.sh (the real Terminal texts, used for the demo).
Outputs: site/index.html, site/<lang>/index.html, site/404.html,
         site/sitemap.xml, site/robots.txt, site/_redirects, site/_headers.

Every language must have every English key; the build fails on a missing
or unknown key, or if a {{token}} is left over.
"""
import base64
import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "site-src"
OUT = ROOT / "site"
BASE = "https://macup.cdav.io"
REPO_RAW = "https://raw.githubusercontent.com/CDAVIO/MacUp-Cleaner-CDAV.IO/main/install.sh"
INSTALL_CMD = f"curl -fsSL {REPO_RAW} | bash"
LANGS = ["en", "ro", "de", "it", "fr", "ko", "zh"]
LEGAL_PAGES = [("terms", "Terms of Use"), ("privacy", "Privacy Policy"), ("legal", "Legal Notice")]

# Footer social icons. To add LinkedIn or Instagram, move its line out of the
# comment and put the real profile address in.
ICON_GITHUB = ('<path d="M12 2a10 10 0 0 0-3.2 19.5c.5.1.7-.2.7-.5v-1.7c-2.8.6-3.4-1.2-3.4-1.2-.5-1.2-1.1-1.5-1.1-1.5-.9-.6.1-.6.1-.6 '
               '1 .1 1.5 1 1.5 1 .9 1.6 2.4 1.1 3 .9.1-.7.4-1.1.6-1.4-2.2-.3-4.6-1.1-4.6-5 0-1.1.4-2 1-2.7-.1-.3-.4-1.3.1-2.7 0 0 '
               '.8-.3 2.8 1a9.6 9.6 0 0 1 5 0c1.9-1.3 2.8-1 2.8-1 .5 1.4.2 2.4.1 2.7.6.7 1 1.6 1 2.7 0 3.9-2.3 4.7-4.6 5 .4.3.7.9.7 '
               '1.9V21c0 .3.2.6.7.5A10 10 0 0 0 12 2Z"/>')
ICON_LINKEDIN = ('<path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM3 9.75h4V21H3V9.75Zm6.5 0h3.8v1.6h.06c.53-1 1.83-2.05 '
                 '3.77-2.05 4.03 0 4.77 2.65 4.77 6.1V21h-4v-4.98c0-1.19-.02-2.72-1.66-2.72-1.66 0-1.92 1.3-1.92 2.63V21h-4V9.75Z"/>')
ICON_INSTAGRAM = ('<path d="M12 7.3a4.7 4.7 0 1 0 0 9.4 4.7 4.7 0 0 0 0-9.4Zm0 7.7a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm4.9-8.98a1.1 1.1 0 1 1 '
                  '0 2.2 1.1 1.1 0 0 1 0-2.2ZM12 3.6c2.3 0 2.57 0 3.48.05 2.34.1 3.43 1.21 3.53 3.53.04.9.05 1.18.05 3.48s0 '
                  '2.57-.05 3.48c-.1 2.32-1.19 3.43-3.53 3.53-.9.04-1.18.05-3.48.05s-2.57 0-3.48-.05c-2.34-.1-3.43-1.21-3.53-3.53C4.95 '
                  '14.57 4.94 14.3 4.94 12s0-2.57.05-3.48c.1-2.32 1.19-3.43 3.53-3.53.9-.04 1.18-.05 3.48-.05ZM12 2c-2.34 0-2.63 '
                  '0-3.55.05-3.15.15-4.9 1.89-5.05 5.05C3.35 8.02 3.34 8.31 3.34 12s0 2.63.06 3.55c.14 3.15 1.89 4.9 5.05 5.05.92.04 '
                  '1.21.06 3.55.06s2.63 0 3.55-.06c3.15-.14 4.9-1.89 5.05-5.05.04-.92.06-1.21.06-3.55s0-2.63-.06-3.55c-.14-3.15-1.89-4.9-5.05-5.05C14.63 '
                  '2.01 14.34 2 12 2Z"/>')
SOCIAL = [
    ("GitHub", "https://github.com/CDAVIO", ICON_GITHUB),
    # ("LinkedIn", "https://www.linkedin.com/in/…", ICON_LINKEDIN),
    # ("Instagram", "https://www.instagram.com/…", ICON_INSTAGRAM),
]
HTML_LANG = {"zh": "zh-Hans"}
CLI_KEY = re.compile(r"^S_([a-z_0-9]+)='(.*)'$", re.M)


def load_site(code):
    return json.loads((SRC / "strings" / f"{code}.json").read_text())


def load_cli(code):
    return dict(CLI_KEY.findall((ROOT / "lib" / "lang" / f"{code}.sh").read_text()))


def fill(text, *args):
    for i, a in enumerate(args, 1):
        text = text.replace("{%d}" % i, str(a))
    return text


E = html.escape


# ── Demo (the animated Terminal) ─────────────────────────────────────────
def demo(c, s):
    """Chapters of lines; every visible text comes from the CLI strings."""
    t = lambda k, *a: fill(c[k], *a)  # noqa: E731
    title = lambda n, k: {"k": "title", "n": n, "t": c[k]}  # noqa: E731
    rule = {"k": "rule"}
    blank = {"k": "blank"}
    dim = lambda text: {"k": "text", "t": text, "c": "dim"}  # noqa: E731
    group = lambda k: {"k": "group", "t": c[k]}  # noqa: E731

    def row(icon, label, value, extra="", bar=None, state="info"):
        r = {"k": "row", "i": icon, "s": state, "l": label, "v": value}
        if extra:
            r["x"] = extra
        if bar is not None:
            r["b"] = bar
        return r

    ok = lambda l, v, x="", b=None: row("✓", l, v, x, b, "ok")  # noqa: E731
    warn = lambda l, v, x="", b=None: row("!", l, v, x, b, "warn")  # noqa: E731
    info = lambda l, v, x="", b=None: row("·", l, v, x, b, "info")  # noqa: E731

    def opt(n, on, key, size, hint):
        return {"k": "opt", "n": n, "on": on, "l": c[key], "v": size, "x": c[hint]}

    def score(key, pct, extra=""):
        return {"k": "score", "l": c[key], "p": pct, "x": extra}

    def rec(icon, state, ttl, detail, cmd=""):
        return {"k": "rec", "i": icon, "s": state, "t": ttl, "d": detail, "c": cmd}

    clean = [
        title("1", "clean_title"), rule, dim(c["clean_intro_1"]), dim(c["clean_intro_2"]), blank,
        {"k": "spin", "t": c["scanning"], "ms": 1300},
        opt("1", True, "cat_app_caches", "3.1 GB", "hint_rebuilds"),
        opt("2", True, "cat_browser_caches", "2.4 GB", "hint_rebuilds"),
        opt("3", True, "cat_logs", "412.6 MB", "hint_safe"),
        opt("4", True, "cat_reports", "96.3 MB", "hint_safe"),
        opt("5", False, "cat_developer", "2.6 GB", "hint_developer"),
        opt("6", False, "cat_history", "58.1 MB", "hint_history"),
        opt("7", False, "cat_saved_state", "12.4 MB", "hint_saved_state"),
        rule,
        {"k": "text", "t": f'{c["selected"]} 6.0 GB  {c["goes_to_trash"]}', "c": "b"},
        blank, dim(c["clean_prompt"]), {"k": "input", "t": "⏎"},
        {"k": "spin", "t": c["cleaning"], "ms": 1400},
        ok(c["cat_app_caches"], c["status_done"]),
        ok(c["cat_browser_caches"], c["status_done"]),
        ok(c["cat_logs"], c["status_done"]),
        ok(c["cat_reports"], c["status_done"]),
        rule,
        {"k": "text", "t": f'{c["moved_total"]} 6.0 GB', "c": "y b"},
        dim(c["empty_trash_note"]),
    ]
    mac = [
        title("2", "mac_title"), rule, {"k": "text", "t": "MacBook Air  ·  Apple M3  ·  macOS 15", "c": "b"}, blank,
        group("part_storage"),
        info(c["k_used"], "431.2 GB / 494.4 GB", b=87),
        warn(c["k_free"], "63.2 GB  (13%)"),
        warn(c["k_hidden_cache"], "8.6 GB"),
        group("part_ssd"),
        info(c["k_model"], "APPLE SSD AP0512Z"),
        ok("S.M.A.R.T.", "Verified"),
        ok(c["k_ssd_health"], t("ssd_wear_value", 97)),
        group("part_battery"),
        ok(c["k_bat_health"], "91%  Normal", b=91),
        info(c["k_cycles"], f'312  {c["cycles_hint"]}'),
        info(c["k_charge"], f'78%  {c["charging"]}', b=78),
        group("part_memory"),
        info(c["k_ram"], "16 GB"),
        ok(c["k_mem_free"], "38%", b=38),
        ok(c["k_swap"], "0.4 GB"),
        group("part_cpu"),
        info(c["k_chip"], "Apple M3"),
        info(c["k_cores"], t("cores_split", 8, 4, 4)),
        ok(c["k_load"], "18%", b=18),
        ok(c["k_heat"], c["heat_ok"]),
        ok(c["k_uptime"], t("days", 3)),
        group("part_gpu"),
        info(c["k_gpu"], f'Apple M3 · {t("gpu_cores", 10)}'),
        info(c["k_displays"], "Color LCD (2560 x 1664 @ 60Hz)"),
        blank, dim(c["mac_tip"]),
    ]
    protect = [
        title("3", "protection_title"), rule, dim(c["protection_intro"]), blank,
        ok("Gatekeeper", c["on"], c["p_gatekeeper_d"]),
        ok(c["p_sip"], c["on"], c["p_sip_d"]),
        ok("FileVault", c["on"], c["p_filevault_d"]),
        warn(c["p_firewall"], c["off"], c["fix_firewall"]),
        ok("XProtect", c["on"], t("p_xprotect_d", "5368")),
        ok(c["p_responses"], c["on"], c["p_responses_d"]),
        ok(c["p_autoupdate"], c["on"], c["p_autoupdate_d"]),
        rule,
        score("part_protection", 85, "6/7"),
        blank, dim(c["antivirus_note_1"]), dim(c["antivirus_note_2"]),
    ]
    perf = [
        title("4", "performance_title"), rule,
        ok(c["k_load"], "18%", b=18),
        ok(c["k_heat"], c["heat_ok"]),
        ok(c["k_uptime"], t("days", 3)),
        group("top_cpu"),
        {"k": "proc", "l": "Safari", "v": "12.4%"},
        {"k": "proc", "l": "Photos", "v": "6.1%"},
        {"k": "proc", "l": "Mail", "v": "2.3%"},
        group("top_memory"),
        {"k": "proc", "l": "Safari", "v": "1.8 GB"},
        {"k": "proc", "l": "Xcode", "v": "1.2 GB"},
        {"k": "proc", "l": "Music", "v": "0.6 GB"},
        blank,
        info(c["k_startup"], "9"),
        warn(c["k_startup_broken"], "2"),
        dim(c["startup_broken_hint"]),
        blank, dim(c["perf_tip"]),
    ]
    check = [
        title("5", "check_title"), rule, dim(c["check_intro"]),
        {"k": "spin", "t": c["checking"], "ms": 1700},
        {"k": "big", "l": c["battery_health"], "p": 91, "g": f'{c["k_cycles"]}: 312'},
        blank,
        warn(c["part_storage"], f'{t("note_storage", "63.2 GB", 13)}  · {c["grade_attention"]}'),
        ok(c["part_ssd"], f'S.M.A.R.T.: Verified  · {c["grade_good"]}'),
        ok(c["part_battery"], f'{c["k_bat_health"]} 91% · {c["k_cycles"]}: 312  · {c["grade_good"]}'),
        ok(c["part_memory"], f'{t("note_memory", 38, 0)}  · {c["grade_good"]}'),
        ok(c["part_cpu"], f'{t("note_cpu", 18, 3)}  · {c["grade_good"]}'),
        warn(c["part_protection"], f'{t("note_protection", 6, 7)}  · {c["grade_attention"]}'),
        warn(c["part_cleanup"], f'8.6 GB  · {c["grade_attention"]}'),
        blank,
        {"k": "group", "t": "→  " + c["report_recs"]},
        rec("✕", "bad", t("rec_space_low", 13), c["rec_space_low_d"], "$ macup clean"),
        rec("!", "warn", t("rec_cache", "8.6 GB"), c["rec_cache_d"], "$ macup clean"),
        rec("!", "warn", c["rec_firewall"], c["rec_firewall_d"]),
        rule,
        {"k": "spin", "t": c["making_pdf"], "ms": 1200},
        {"k": "saved", "t": c["pdf_saved"], "p": "~/Downloads/MacUp-Health-Report-2026-10-31-1720.pdf"},
    ]
    chapters = [
        {"cmd": "macup clean", "cap": s["demo_cap_1"], "lines": clean},
        {"cmd": "macup mac", "cap": s["demo_cap_2"], "lines": mac},
        {"cmd": "macup protect", "cap": s["demo_cap_3"], "lines": protect},
        {"cmd": "macup perf", "cap": s["demo_cap_4"], "lines": perf},
        {"cmd": "macup check", "cap": s["demo_cap_5"], "lines": check},
        {"cmd": "", "cap": s["demo_cap_6"], "pdf": True, "lines": []},
    ]
    return json.dumps({"chapters": chapters}, ensure_ascii=False).replace("</", "<\\/")


# ── Report mock-ups ──────────────────────────────────────────────────────
def pdf_mock(c):
    t = lambda k, *a: fill(c[k], *a)  # noqa: E731
    cards = [
        ("warn", c["part_storage"], "63.2 GB", t("note_storage", "63.2 GB", 13)),
        ("ok", c["part_ssd"], "Verified", "S.M.A.R.T.: Verified"),
        ("ok", c["part_battery"], "91%", f'{c["k_bat_health"]} 91% · {c["k_cycles"]}: 312'),
        ("ok", c["part_memory"], "16 GB", t("note_memory", 38, 0)),
        ("ok", c["part_cpu"], t("gpu_cores", 8), t("note_cpu", 18, 3)),
        ("warn", c["part_protection"], "6/7", t("note_protection", 6, 7)),
    ]
    tiles = []
    for state, label, big, note in cards:
        pill = (f'<i class="pill ok">✓ {E(c["grade_good"])}</i>' if state == "ok"
                else f'<i class="pill warn">! {E(c["grade_attention"])}</i>')
        tiles.append(
            f'<div class="tile {state}"><span class="th"><small>{E(label)}</small>{pill}</span>'
            f'<b>{E(big)}</b><em>{E(note)}</em></div>'
        )
    return (
        '<div class="paper dark"><div class="pp">'
        '<div class="pp-head"><span class="pp-logo">✦ MacUp</span><span>2026-10-31</span></div>'
        f'<h4>{E(c["report_title"])}</h4><p class="pp-sub">MacBook Air · Apple M3 · macOS 15</p>'
        '<div class="pp-score"><div class="ring" style="--p:91"><div><b>91<i>%</i></b>'
        f'<span>{E(c["grade_good"])}</span></div></div>'
        f'<p><strong>{E(c["battery_health"])}</strong><span class="y">{E(c["k_cycles"])}: 312</span>'
        f'{E(c["report_cache"])} <b class="y">8.6 GB</b></p></div>'
        f'<div class="tiles">{"".join(tiles)}</div></div></div>'
    )


def details_mock(c):
    rows = [(c["part_storage"], 87), (c["part_battery"], 91), (c["part_memory"], 62),
            (c["part_cpu"], 18), ("SSD", 100), (c["part_gpu"], 100)]
    return "".join(
        f'<span class="dl"><em>{E(k)}</em><span class="tb"><span style="--p:{p}%"></span></span></span>'
        for k, p in rows
    )


def recs_mock(c):
    items = [fill(c["rec_space_low"], 13), fill(c["rec_cache"], "8.6 GB"), c["rec_firewall"]]
    out = "".join(f'<span class="ri"><i>{i}</i>{E(x)}</span>' for i, x in enumerate(items, 1))
    return out + f'<span class="good-box">{E(c["good_title"])}</span>'


# ── Page assembly ────────────────────────────────────────────────────────
def footer(site, home):
    repo = "https://github.com/CDAVIO/MacUp-Cleaner-CDAV.IO"
    links = [("/terms/", site["footer_terms"]), ("/privacy/", site["footer_privacy_policy"]),
             ("/legal/", site["footer_legal"]), (f"{repo}/blob/main/LICENSE", site["footer_license"]),
             (f"{repo}/blob/main/SECURITY.md", site["footer_security"])]
    nav = "".join(f'<a href="{href}">{E(label)}</a>' for href, label in links)
    social = "".join(
        f'<li><a href="{url}" aria-label="{name}" title="{name}" rel="me noopener">'
        f'<svg viewBox="0 0 24 24" aria-hidden="true">{icon}</svg></a></li>'
        for name, url, icon in SOCIAL
    )
    return (
        '<footer class="foot">\n  <div class="wrap foot-in">\n'
        f'    <a class="brand" href="{home}"><img src="/favicon.svg" alt="" width="26" height="26"><span>MacUp</span></a>\n'
        f'    <nav class="foot-links" aria-label="Footer">{nav}</nav>\n'
        '    <div class="fine">\n'
        f'      <p>Copyright © 2026 <a href="https://cdav.io">CDAV.IO</a>. {E(site["footer_rights"])}</p>\n'
        f'      <ul class="social">{social}</ul>\n'
        '    </div>\n  </div>\n</footer>'
    )


def url_for(code):
    return f"{BASE}/" if code == "en" else f"{BASE}/{code}/"


REDIRECT_JS = (
    'try { if (location.pathname === "/" && !localStorage.getItem("macup-lang")) {'
    ' var l = ((navigator.languages && navigator.languages[0]) || navigator.language || "").toLowerCase().slice(0, 2);'
    ' if (["ro","de","it","fr","ko","zh"].indexOf(l) > -1) location.replace("/" + l + "/" + location.hash); } } catch (e) {}'
)


def build_page(template, code, en_site, en_cli, asset_v):
    site = {**en_site, **load_site(code)}
    cli = {**en_cli, **load_cli(code)}
    unknown = set(load_site(code)) - set(en_site)
    if unknown:
        sys.exit(f"{code}.json has keys English doesn't have: {sorted(unknown)}")
    missing = set(en_site) - set(load_site(code))
    if missing:
        sys.exit(f"{code}.json is missing: {sorted(missing)}")

    alternates = "\n".join(
        f'<link rel="alternate" hreflang="{HTML_LANG.get(l, l)}" href="{url_for(l)}">' for l in LANGS
    ) + f'\n<link rel="alternate" hreflang="x-default" href="{url_for("en")}">'
    items = "".join(
        f'<li role="none"><a role="menuitem" href="{"/" if l == "en" else f"/{l}/"}" hreflang="{HTML_LANG.get(l, l)}" '
        f'lang="{HTML_LANG.get(l, l)}" data-lang="{l}"{' aria-current="page"' if l == code else ""}>'
        f'{E(load_site(l)["lang_name"])}</a></li>'
        for l in LANGS
    )
    ld = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "MacUp",
        "applicationCategory": "UtilitiesApplication",
        "operatingSystem": "macOS 13 or later",
        "description": site["meta_desc"],
        "url": url_for(code),
        "inLanguage": HTML_LANG.get(code, code),
        "license": "https://opensource.org/licenses/MIT",
        "codeRepository": "https://github.com/CDAVIO/MacUp-Cleaner-CDAV.IO",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
    }
    special = {
        "html_lang": HTML_LANG.get(code, code),
        "canonical": url_for(code),
        "home": "/" if code == "en" else f"/{code}/",
        "alternates": alternates,
        "lang_items": items,
        "lang_redirect": REDIRECT_JS if code == "en" else "",
        "ld_json": json.dumps(ld, ensure_ascii=False).replace("</", "<\\/"),
        "demo_json": demo(cli, site),
        "pdf_mock": pdf_mock(cli),
        "details_mock": details_mock(cli),
        "recs_mock": recs_mock(cli),
        "install_cmd": E(INSTALL_CMD),
        "footer": footer(site, "/" if code == "en" else f"/{code}/"),
        "asset_v": asset_v,
    }

    def sub(m):
        key = m.group(1)
        if key in special:
            return special[key]
        if key.startswith("cli."):
            return E(cli[key[4:]])
        if key in site:
            return E(site[key])
        sys.exit(f"Unknown token {{{{{key}}}}} ({code})")

    out = re.sub(r"\{\{([a-z_0-9.]+)\}\}", sub, template)
    if "{{" in out:
        sys.exit(f"Leftover token in {code}")
    return out


def inline_script_hash(page):
    body = re.search(r"<script>(.*?)</script>", page, re.S).group(1)
    return "'sha256-" + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode() + "'"


def main():
    template = (SRC / "template.html").read_text()
    en_site, en_cli = load_site("en"), load_cli("en")
    asset_v = hashlib.sha256(
        (OUT / "assets" / "style.css").read_bytes() + (OUT / "assets" / "app.js").read_bytes()
    ).hexdigest()[:10]

    hashes = set()
    for code in LANGS:
        page = build_page(template, code, en_site, en_cli, asset_v)
        hashes.add(inline_script_hash(page))
        dest = OUT / ("index.html" if code == "en" else f"{code}/index.html")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page)

    # Legal pages (English), sharing the header style, footer and CSP-hashed theme script.
    theme_js = re.search(r"<script>(.*?)</script>", template, re.S).group(1).replace("{{lang_redirect}}", "")
    for slug, title in LEGAL_PAGES:
        body = (SRC / "legal" / f"{slug}.html").read_text()
        page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)} — MacUp</title>
<meta name="description" content="{E(title)} for MacUp, the free Mac health tool for the Terminal.">
<link rel="canonical" href="{BASE}/{slug}/">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<script>{theme_js}</script>
<link rel="stylesheet" href="/assets/style.css?v={asset_v}">
</head>
<body>
<header class="top">
  <div class="wrap top-in">
    <a class="brand" href="/" aria-label="MacUp"><img src="/favicon.svg" alt="" width="30" height="30"><span>MacUp</span></a>
    <nav class="nav" aria-label="Main"><a href="/terms/">Terms</a><a href="/privacy/">Privacy</a><a href="/legal/">Legal</a></nav>
    <div class="tools">
      <button class="icon-btn" id="theme" type="button" aria-label="Switch light / dark" title="Switch light / dark">
        <svg class="i-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M4.6 4.6l1.6 1.6M17.8 17.8l1.6 1.6M2.5 12h2.2M19.3 12h2.2M4.6 19.4l1.6-1.6M17.8 6.2l1.6-1.6"/></svg>
        <svg class="i-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z"/></svg>
      </button>
    </div>
  </div>
</header>
<main id="main" class="wrap legal">
<article>
{body}
</article>
</main>
{footer(en_site, "/")}
<script src="/assets/app.js?v={asset_v}" defer></script>
</body>
</html>
"""
        if "{{" in page:
            sys.exit(f"Leftover token in {slug}")
        hashes.add(inline_script_hash(page))
        dest = OUT / slug / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page)

    s = en_site
    (OUT / "404.html").write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(s["not_found_t"])} — MacUp</title><meta name="robots" content="noindex">
<meta name="color-scheme" content="light dark"><link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/style.css?v={asset_v}"></head>
<body class="nf"><main class="wrap nf-in"><img src="/favicon.svg" alt="" width="64" height="64">
<h1>404 · {E(s["not_found_t"])}</h1><p class="lead">{E(s["not_found_d"])}</p>
<a class="btn" href="/">{E(s["not_found_btn"])}</a></main></body></html>
""")

    urls = "".join(
        f"  <url><loc>{url_for(c)}</loc>"
        + "".join(f'<xhtml:link rel="alternate" hreflang="{HTML_LANG.get(l, l)}" href="{url_for(l)}"/>' for l in LANGS)
        + "</url>\n"
        for c in LANGS
    )
    urls += "".join(f"  <url><loc>{BASE}/{slug}/</loc></url>\n" for slug, _ in LEGAL_PAGES)
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        f"{urls}</urlset>\n"
    )
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")

    # Old pages of the paid app go to the home page; install.sh is served from GitHub.
    (OUT / "_redirects").write_text(f"""/install.sh       {REPO_RAW}  200
/download         /  301
/download.html    /  301
/success          /  301
/success.html     /  301
/license          /  301
/license.html     /terms/  301
/privacy.html     /privacy/  301
/help.html        /#faq  301
/security.html    https://github.com/CDAVIO/MacUp-Cleaner-CDAV.IO/blob/main/SECURITY.md  301
/version.json     /  301
/api/*            /  301
""")
    csp = (
        "default-src 'self'; "
        f"script-src 'self' {' '.join(sorted(hashes))}; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
        "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'"
    )
    (OUT / "_headers").write_text(f"""/*
  Content-Security-Policy: {csp}
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=()
  Strict-Transport-Security: max-age=31536000; includeSubDomains
  X-Frame-Options: DENY

/assets/*
  Cache-Control: public, max-age=31536000, immutable
""")
    print(f"Built {len(LANGS)} pages · assets v{asset_v}")


if __name__ == "__main__":
    main()
