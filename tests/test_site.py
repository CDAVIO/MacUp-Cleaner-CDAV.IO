"""Checks for the website sources (site-src/) and the built pages (site/)."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LANGS = ["en", "ro", "de", "it", "fr", "ko", "zh"]


def strings(code):
    return json.loads((ROOT / "site-src" / "strings" / f"{code}.json").read_text())


@pytest.mark.parametrize("code", LANGS[1:])
def test_every_language_has_every_website_text(code):
    assert sorted(strings(code)) == sorted(strings("en"))
    assert all(isinstance(v, str) and v.strip() for v in strings(code).values())


def test_build_is_up_to_date_and_complete():
    before = {p: p.read_bytes() for p in (ROOT / "site").rglob("*.html")}
    out = subprocess.run([sys.executable, str(ROOT / "site-src" / "build.py")], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr + out.stdout
    after = {p: p.read_bytes() for p in (ROOT / "site").rglob("*.html")}
    assert before == after, "site/ was out of date — commit the rebuilt pages"
    for code in LANGS:
        page = ROOT / "site" / ("index.html" if code == "en" else f"{code}/index.html")
        html = page.read_text()
        assert "{{" not in html
        assert "raw.githubusercontent.com/CDAVIO/MacUp-Cleaner-CDAV.IO/main/install.sh" in html
        demo = re.search(r'<script type="application/json" id="demo-data">(.*?)</script>', html, re.S)
        assert len(json.loads(demo.group(1))["chapters"]) == 6


def test_site_has_no_prices_or_payment_leftovers():
    for page in (ROOT / "site").rglob("*.html"):
        text = page.read_text()
        assert "9.99" not in text and "9,99" not in text, page
        assert "stripe" not in text.lower(), page
        assert "license key" not in text.lower(), page


def test_site_names_no_security_vendor():
    # The site explains antivirus honestly but never names a company.
    vendors = ["bitdefender", "norton", "mcafee", "kaspersky", "avast", "avg ", "intego", "malwarebytes", "cleanmymac", "macpaw"]
    for page in (ROOT / "site").rglob("*.html"):
        text = page.read_text().lower()
        for v in vendors:
            assert v not in text, (page, v)
