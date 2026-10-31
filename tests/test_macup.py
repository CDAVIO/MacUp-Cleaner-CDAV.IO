"""Tests for the MacUp Terminal tool (macup, lib/, install.sh)."""
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MACUP = ROOT / "macup"
LANGS = ["en", "ro", "de", "it", "fr", "ko", "zh"]
KEY = re.compile(r"^(S_[a-z_0-9]+)='(.*)'$", re.M)


def lang_strings(code):
    return dict(KEY.findall((ROOT / "lib" / "lang" / f"{code}.sh").read_text()))


def run(args, home, env=None, timeout=120, stdin=subprocess.DEVNULL):
    e = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "en_US.UTF-8",
        "TMPDIR": str(home / "tmp"),
        "SHELL": "/bin/zsh",
    }
    (home / "tmp").mkdir(parents=True, exist_ok=True)
    e.update(env or {})
    return subprocess.run(
        args, env=e, stdin=stdin, capture_output=True, text=True, timeout=timeout
    )


def bash(script):
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, timeout=30
    )


# ── Languages ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("code", LANGS[1:])
def test_language_has_every_english_key_with_same_placeholders(code):
    en = lang_strings("en")
    other = lang_strings(code)
    assert sorted(other) == sorted(en)
    for key, text in en.items():
        assert sorted(re.findall(r"\{\d\}", other[key])) == sorted(
            re.findall(r"\{\d\}", text)
        ), key


@pytest.mark.parametrize("code", LANGS)
def test_language_file_values_are_plain_strings(code):
    source = (ROOT / "lib" / "lang" / f"{code}.sh").read_text()
    for line in source.splitlines():
        if line.startswith("S_"):
            assert KEY.match(line), line
            value = KEY.match(line).group(2)
            # No ASCII quote, $ or backtick inside a value: they would break or expand.
            assert "'" not in value and "$" not in value and "`" not in value, line
            assert value.strip(), line


def test_every_used_string_is_defined():
    sources = "\n".join(
        p.read_text() for p in [MACUP, *sorted((ROOT / "lib").glob("*.sh"))]
    )
    used = set(re.findall(r'\$\(t "?([a-z_0-9]+)', sources))
    used |= set(re.findall(r"(?:^|[\s;(|&])t ([a-z_0-9]+)", sources, re.M))
    defined = {k[2:] for k in lang_strings("en")}
    assert used, "no t calls found"
    assert used - defined == set()


def test_t_fills_placeholders_and_falls_back_to_english():
    out = bash(
        f'MACUP_ROOT="{ROOT}"; . "{ROOT}/lib/i18n.sh"; i18n_load ro; '
        't days 5; echo; t unknown_command "x y"; echo; '
        'i18n_load xx; t quit'
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.splitlines() == ["5 zile", "Comandă necunoscută: x y", "Quit"]


# ── Scripts ──────────────────────────────────────────────────────────────


def test_all_shell_scripts_parse():
    scripts = [MACUP, ROOT / "install.sh", ROOT / "pdf" / "build.sh"]
    scripts += sorted((ROOT / "lib").rglob("*.sh"))
    for script in scripts:
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, f"{script}: {result.stderr}"


def test_version_command_matches_version_file(tmp_path):
    out = run([str(MACUP), "--version"], tmp_path)
    assert out.returncode == 0, out.stderr
    assert (ROOT / "VERSION").read_text().strip() in out.stdout


@pytest.mark.parametrize("code", LANGS)
def test_help_works_in_every_language(tmp_path, code):
    out = run([str(MACUP), "--lang", code, "--no-color", "help"], tmp_path)
    assert out.returncode == 0, out.stderr
    assert "macup clean" in out.stdout and "macup check" in out.stdout
    assert lang_strings(code)["S_help_menu"] in out.stdout


def test_unknown_command_fails_cleanly(tmp_path):
    out = run([str(MACUP), "--no-color", "nonsense"], tmp_path)
    assert out.returncode != 0
    assert "nonsense" in out.stdout + out.stderr


# ── Scores ───────────────────────────────────────────────────────────────


def score(fn, **values):
    assigns = " ".join(f"{k}={v!r}" for k, v in values.items())
    out = bash(f'. "{ROOT}/lib/checks.sh"; {assigns}; {fn}')
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


@pytest.mark.parametrize(
    "free,expected", [(50, "100"), (25, "100"), (15, "80"), (10, "60"), (6, "36"), (0, "10")]
)
def test_storage_score(free, expected):
    assert score("score_storage", H_DISK_FREE_PCT=free) == expected


def test_ssd_score():
    assert score("score_ssd", H_SSD_SMART="Verified", H_SSD_WEAR="") == "100"
    assert score("score_ssd", H_SSD_SMART="Verified", H_SSD_WEAR="12") == "88"
    assert score("score_ssd", H_SSD_SMART="Failing", H_SSD_WEAR="") == "10"
    assert score("score_ssd", H_SSD_SMART="", H_SSD_WEAR="") == ""


def test_battery_score():
    assert score("score_battery", H_BAT="0") == ""
    assert score("score_battery", H_BAT="1", H_BAT_HEALTH="93", H_BAT_CONDITION="Normal") == "93"
    assert score("score_battery", H_BAT="1", H_BAT_HEALTH="90", H_BAT_CONDITION="Service Recommended") == "55"


def test_memory_and_cpu_scores():
    assert score("score_memory", H_MEM_FREE_PCT=40, H_SWAP_MB=0) == "100"
    assert score("score_memory", H_MEM_FREE_PCT=37, H_SWAP_MB=19000) == "80"
    assert score("score_memory", H_MEM_FREE_PCT=2, H_SWAP_MB=9000) == "10"
    cpu = dict(H_CPU_LOAD_PCT=10, H_THERMAL_WARN=0, H_UPTIME_DAYS=1)
    assert score("score_cpu", **cpu) == "100"
    assert score("score_cpu", **{**cpu, "H_CPU_LOAD_PCT": 100}) == "70"
    assert score("score_cpu", **{**cpu, "H_THERMAL_WARN": 1, "H_UPTIME_DAYS": 40}) == "70"


def test_protection_and_cleanup_scores():
    assert score("score_protection", P_PASSED=7, P_TOTAL=7) == "100"
    assert score("score_protection", P_PASSED=5, P_TOTAL=7) == "71"
    assert score("score_cleanup", H_CLEANABLE=500000000) == "100"
    assert score("score_cleanup", H_CLEANABLE=25000000000) == "65"


# ── Smart Clean (Trash only) ─────────────────────────────────────────────


def make_cache(home):
    cache = home / "Library" / "Caches" / "com.example.macup-test"
    cache.mkdir(parents=True)
    (cache / "blob.bin").write_bytes(os.urandom(256 * 1024))
    return cache


def test_clean_without_terminal_only_previews(tmp_path):
    cache = make_cache(tmp_path)
    out = run([str(MACUP), "--no-color", "clean"], tmp_path, timeout=300)
    assert out.returncode == 0, out.stderr
    assert (cache / "blob.bin").exists()
    trash = tmp_path / ".Trash"
    assert not trash.exists() or not any(trash.iterdir())


def test_clean_with_yes_moves_to_trash_never_deletes(tmp_path):
    cache = make_cache(tmp_path)
    data = (cache / "blob.bin").read_bytes()
    out = run([str(MACUP), "--no-color", "--yes", "clean"], tmp_path, timeout=300)
    assert out.returncode == 0, out.stderr + out.stdout
    # The app's cache folder stays; what was inside it goes to the Trash.
    assert not (cache / "blob.bin").exists()
    trashed = [p for p in (tmp_path / ".Trash").rglob("blob.bin")]
    assert len(trashed) == 1
    assert trashed[0].read_bytes() == data


# ── Installer ────────────────────────────────────────────────────────────


def install(home, extra=None):
    env = {
        "MACUP_SOURCE": str(ROOT),
        "MACUP_BIN_DIR": str(home / ".local" / "bin"),
    }
    env.update(extra or {})
    return run(["bash", str(ROOT / "install.sh")], home, env=env)


def test_install_update_and_uninstall(tmp_path):
    out = install(tmp_path)
    assert out.returncode == 0, out.stderr + out.stdout
    dest = tmp_path / ".macup"
    assert sorted(p.name for p in dest.iterdir()) == sorted(
        ["macup", "VERSION", "LICENSE", "THIRD_PARTY_NOTICES.md", "lib", "engine", "bin"]
    )
    link = tmp_path / ".local" / "bin" / "macup"
    assert link.is_symlink() and os.readlink(link) == str(dest / "macup")
    zprofile = (tmp_path / ".zprofile").read_text()
    assert zprofile.count("# added by MacUp") == 1

    version = run([str(link), "--version"], tmp_path)
    assert version.returncode == 0, version.stderr
    assert (ROOT / "VERSION").read_text().strip() in version.stdout

    # Running it again updates in place without duplicating anything.
    again = install(tmp_path)
    assert again.returncode == 0, again.stderr + again.stdout
    assert (tmp_path / ".zprofile").read_text().count("# added by MacUp") == 1
    assert not list(tmp_path.glob(".macup.*"))

    gone = run([str(link), "--yes", "--no-color", "uninstall"], tmp_path)
    assert gone.returncode == 0, gone.stderr + gone.stdout
    assert not dest.exists()
    assert not link.exists() and not link.is_symlink()
    assert "# added by MacUp" not in (tmp_path / ".zprofile").read_text()


def test_install_refuses_to_replace_a_folder_that_is_not_macup(tmp_path):
    mine = tmp_path / ".macup"
    mine.mkdir()
    (mine / "notes.txt").write_text("keep me")
    out = install(tmp_path)
    assert out.returncode != 0
    assert (mine / "notes.txt").read_text() == "keep me"


def test_install_refuses_to_replace_another_macup_command(tmp_path):
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "macup").write_text("#!/bin/sh\necho other\n")
    out = install(tmp_path)
    assert out.returncode != 0
    assert (bin_dir / "macup").read_text() == "#!/bin/sh\necho other\n"


# ── Complete check + PDF ─────────────────────────────────────────────────


def test_complete_check_saves_a_three_page_pdf(tmp_path):
    (tmp_path / "Downloads").mkdir()
    out = run([str(MACUP), "--no-color", "check"], tmp_path, timeout=300)
    assert out.returncode == 0, out.stderr + out.stdout
    assert re.search(r"\d+%", out.stdout)
    pdfs = list((tmp_path / "Downloads").glob("MacUp-Health-Report-*.pdf"))
    assert len(pdfs) == 1, out.stdout
    data = pdfs[0].read_bytes()
    assert data.startswith(b"%PDF")
    assert len(re.findall(rb"/Type\s*/Page[^s]", data)) == 3
