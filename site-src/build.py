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
        {"k": "big", "l": c["mac_health"], "p": 89, "g": c["grade_good"]},
        blank,
        score("part_storage", 72), score("part_ssd", 100), score("part_battery", 91),
        score("part_memory", 100), score("part_cpu", 100), score("part_protection", 85),
        score("part_cleanup", 85),
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
TILES = [("part_storage", 72, "note_storage", ("63.2 GB", 13)),
         ("part_ssd", 100, None, ()),
         ("part_battery", 91, "note_battery", (91, 312)),
         ("part_memory", 100, "note_memory", (38, "0.4")),
         ("part_cpu", 100, "note_cpu", (18, 3)),
         ("part_protection", 85, "note_protection", (6, 7))]


def pdf_mock(c):
    tiles = []
    for key, pct, note, args in TILES:
        n = fill(c[note], *args) if note else "SMART: Verified"
        tiles.append(
            f'<div class="tile"><small>{E(c[key])}</small><b>{pct}<i>%</i></b>'
            f'<span class="tb"><span style="--p:{pct}%"></span></span><em>{E(n)}</em></div>'
        )
    return (
        '<div class="paper dark"><div class="pp">'
        '<div class="pp-head"><span class="pp-logo">✦ MacUp</span><span>2026-10-31</span></div>'
        f'<h4>{E(c["report_title"])}</h4><p class="pp-sub">MacBook Air · Apple M3 · macOS 15</p>'
        '<div class="pp-score"><div class="ring" style="--p:89"><div><b>89<i>%</i></b>'
        f'<span>{E(c["grade_good"])}</span></div></div>'
        f'<p>{E(c["report_cache"])} <b class="y">8.6 GB</b></p></div>'
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


def weights(c):
    parts = [("part_storage", 20), ("part_ssd", 15), ("part_battery", 15), ("part_memory", 15),
             ("part_protection", 15), ("part_cpu", 10), ("part_cleanup", 10)]
    return "".join(
        f'<li><span>{E(c[k])}</span><span class="wb"><span style="--p:{w * 5}%"></span></span><b>{w}%</b></li>'
        for k, w in parts
    )


def grades(c):
    return " · ".join([
        f'<b>90%+</b> {E(c["grade_excellent"])}', f'<b>75%+</b> {E(c["grade_good"])}',
        f'<b>55%+</b> {E(c["grade_fair"])}', f'<b>&lt;55%</b> {E(c["grade_attention"])}',
    ])


# ── Page assembly ────────────────────────────────────────────────────────
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
        "weights": weights(cli),
        "grades": grades(cli),
        "install_cmd": E(INSTALL_CMD),
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
/license.html     /  301
/privacy.html     /  301
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
