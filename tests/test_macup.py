"""Tests for the MacUp Terminal tool (macup, lib/, install.sh)."""
import json
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
    assert score("score_memory", H_MEM_FREE_PCT=37, H_SWAP_MB=19000) == "75"
    assert score("score_memory", H_MEM_FREE_PCT=2, H_SWAP_MB=9000) == "5"
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
    assert sorted(p.name for p in (dest / "bin").iterdir()) == ["macup-pdf", "macup-recent"]
    link = tmp_path / ".local" / "bin" / "macup"
    assert link.is_symlink() and os.readlink(link) == str(dest / "macup")
    zshrc = (tmp_path / ".zshrc").read_text()
    assert zshrc.count("# added by MacUp") == 1

    version = run([str(link), "--version"], tmp_path)
    assert version.returncode == 0, version.stderr
    assert (ROOT / "VERSION").read_text().strip() in version.stdout

    # Running it again updates in place without duplicating anything.
    again = install(tmp_path)
    assert again.returncode == 0, again.stderr + again.stdout
    assert (tmp_path / ".zshrc").read_text().count("# added by MacUp") == 1
    assert not list(tmp_path.glob(".macup.*"))

    gone = run([str(link), "--yes", "--no-color", "uninstall"], tmp_path)
    assert gone.returncode == 0, gone.stderr + gone.stdout
    assert not dest.exists()
    assert not link.exists() and not link.is_symlink()
    assert "# added by MacUp" not in (tmp_path / ".zshrc").read_text()


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


# ── Intel / Apple silicon detection (simulated hardware) ─────────────────

INTEL_PROFILE = {
    "SPHardwareDataType": [{"machine_name": "MacBook Pro", "machine_model": "MacBookPro16,1",
                            "cpu_type": "8-Core Intel Core i9", "number_processors": 8}],
    "SPDisplaysDataType": [
        {"sppci_model": "Intel UHD Graphics 630", "spdisplays_vram_shared": "1536 MB"},
        {"sppci_model": "AMD Radeon Pro 5500M", "spdisplays_vram": "4 GB",
         "spdisplays_mtlgpufamilysupport": "spdisplays_metal3",
         "spdisplays_ndrvs": [{"_name": "Color LCD", "_spdisplays_resolution": "3072 x 1920"},
                              {"_name": "LG UltraFine", "_spdisplays_resolution": "3840 x 2160"}]},
    ],
}
M1_PROFILE = {
    "SPHardwareDataType": [{"machine_name": "MacBook Air", "chip_type": "Apple M1",
                            "number_processors": "proc 8:4:4"}],
    "SPDisplaysDataType": [{"sppci_model": "Apple M1", "sppci_cores": "8",
                            "spdisplays_mtlgpufamilysupport": "spdisplays_metal3",
                            "spdisplays_ndrvs": [{"_name": "Color LCD", "_spdisplays_resolution": "2560 x 1600 Retina"}]}],
}


def detect(tmp_path, profile, sysctl):
    """Runs collect_hardware/cpu/gpu with a fake profile and fake sysctl values."""
    (tmp_path / "profile.json").write_text(json.dumps(profile))
    cases = "\n".join(f'    {k}) echo {v!r} ;;' for k, v in sysctl.items())
    script = f'''
MACUP_ROOT="{ROOT}"; . "{ROOT}/lib/i18n.sh"; . "{ROOT}/lib/checks.sh"; i18n_load en
MACUP_TMP="{tmp_path}"
sysctl() {{
  [ "$1" = "-n" ] && shift
  case "$1" in
{cases}
    *) return 1 ;;
  esac
}}
collect_hardware; collect_cpu; collect_gpu
printf '%s|%s|%s|%s|%s|%s|%s\\n' "$H_CHIP" "$H_CORES" "$H_THREADS" "$H_PCORES" "$H_ECORES" "$H_GPU" "$H_DISPLAYS"
printf '%s|%s\\n' "$H_GPU_CORES" "$H_CPU_LOAD_PCT"
'''
    out = bash(script)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip().splitlines()


def test_intel_mac_with_two_gpus(tmp_path):
    hw, extra = detect(tmp_path, INTEL_PROFILE, {
        "hw.physicalcpu": "8", "hw.logicalcpu": "16", "hw.ncpu": "16",
        "vm.loadavg": "{ 8.00 6.00 5.00 }", "kern.boottime": "{ sec = 1, usec = 0 }",
    })
    chip, cores, threads, p, e, gpu, displays = hw.split("|")
    assert chip == "8-Core Intel Core i9"
    assert (cores, threads, p, e) == ("8", "16", "", "")
    assert gpu == "Intel UHD Graphics 630 + AMD Radeon Pro 5500M (4 GB)"
    assert displays == "Color LCD (3072 x 1920) · LG UltraFine (3840 x 2160)"
    # load 8 over 16 logical CPUs = 50%, not 100%.
    assert extra.split("|")[1] == "50"


def test_apple_m1_core_split(tmp_path):
    hw, extra = detect(tmp_path, M1_PROFILE, {
        "hw.physicalcpu": "8", "hw.logicalcpu": "8", "hw.ncpu": "8",
        "hw.perflevel0.physicalcpu": "4", "hw.perflevel1.physicalcpu": "4",
        "vm.loadavg": "{ 2.00 1.00 1.00 }", "kern.boottime": "{ sec = 1, usec = 0 }",
    })
    chip, cores, threads, p, e, gpu, displays = hw.split("|")
    assert (chip, cores, p, e, gpu) == ("Apple M1", "8", "4", "4", "Apple M1")
    assert extra.split("|") == ["8", "25"]


def test_future_chip_with_unexpected_core_layout_skips_the_split(tmp_path):
    profile = json.loads(json.dumps(M1_PROFILE))
    profile["SPHardwareDataType"][0]["chip_type"] = "Apple M6 Max"
    profile["SPHardwareDataType"][0]["number_processors"] = "proc 18:6:8:4"
    hw, _ = detect(tmp_path, profile, {
        "hw.physicalcpu": "18", "hw.logicalcpu": "18", "hw.ncpu": "18",
        "hw.perflevel0.physicalcpu": "6", "hw.perflevel1.physicalcpu": "8",
        "vm.loadavg": "{ 1.00 1.00 1.00 }", "kern.boottime": "{ sec = 1, usec = 0 }",
    })
    chip, cores, threads, p, e, *_ = hw.split("|")
    assert (chip, cores, p, e) == ("Apple M6 Max", "18", "", "")


def test_developer_items_are_read_from_engine_output(tmp_path):
    (tmp_path / "Library" / "Caches").mkdir(parents=True)
    npm = tmp_path / ".npm" / "_cacache"
    npm.mkdir(parents=True)
    (npm / "blob").write_bytes(os.urandom(64 * 1024))
    ollama = tmp_path / ".ollama" / "models"
    ollama.mkdir(parents=True)
    (ollama / "model.bin").write_bytes(os.urandom(64 * 1024))
    out = subprocess.run(
        ["bash", "-c", f'MACUP_ROOT="{ROOT}"; . "{ROOT}/lib/checks.sh"; . "{ROOT}/lib/clean.sh"; '
                       f'd="{tmp_path}/scan"; clean_scan "$d"; clean_dev_items "$d"'],
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "TMPDIR": str(tmp_path)},
        capture_output=True, text=True, timeout=300,
    )
    assert out.returncode == 0, out.stderr
    items = dict(line.split() for line in out.stdout.splitlines())
    assert int(items.get("npm_cache", 0)) > 0
    assert "ollama_models" not in items  # downloaded models are never offered


def test_missing_values_never_show_plutil_errors(tmp_path):
    """macOS 15's plutil prints 'Could not extract value' on stdout and exits 1."""
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "plutil").write_text(
        '#!/bin/bash\n'
        'out=$(/usr/bin/plutil "$@" 2>&1); rc=$?\n'
        'if [ $rc -ne 0 ]; then echo "$5: Could not extract value, error: No value at that key path or invalid key path: $2"; exit 1; fi\n'
        'printf "%s\\n" "$out"\n'
    )
    (fake / "plutil").chmod(0o755)
    (tmp_path / "profile.json").write_text(json.dumps(M1_PROFILE))
    script = f'''
PATH="{fake}:$PATH"
MACUP_ROOT="{ROOT}"; . "{ROOT}/lib/i18n.sh"; . "{ROOT}/lib/checks.sh"; i18n_load en
MACUP_TMP="{tmp_path}"
collect_hardware; collect_gpu; collect_battery; collect_ssd
printf 'GPU=%s\\nDISPLAYS=%s\\nBAT=%s|%s\\nSSD=%s\\n' "$H_GPU" "$H_DISPLAYS" "$H_BAT" "$H_BAT_CYCLES" "$H_SSD_MODEL"
'''
    out = bash(script)
    assert out.returncode == 0, out.stderr
    assert "Could not extract" not in out.stdout and "key path" not in out.stdout, out.stdout
    assert "GPU=Apple M1\n" in out.stdout
    assert "DISPLAYS=Color LCD (2560 x 1600 Retina)\n" in out.stdout
    assert "BAT=0|\n" in out.stdout  # this fake profile has no battery


# ── Real Terminal (pseudo-TTY): spinner, prompts and the 1–5 menu ────────

def run_tty(home, args, answers, quiet=2.5, limit=240):
    """Runs macup in a pseudo-terminal and types each answer when output goes quiet."""
    import pty
    import select
    import time
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "en_US.UTF-8",
           "TERM": "xterm-256color", "TMPDIR": str(home / "tmp"), "SHELL": "/bin/zsh"}
    (home / "tmp").mkdir(parents=True, exist_ok=True)
    pid, fd = pty.fork()
    if pid == 0:
        os.execve(str(MACUP), [str(MACUP), *args], env)
    out = b""

    def settle():
        nonlocal out
        start = last = time.time()
        while time.time() - start < limit:
            r, _, _ = select.select([fd], [], [], 0.2)
            if r:
                try:
                    data = os.read(fd, 65536)
                except OSError:
                    return False
                if not data:
                    return False
                out += data
                last = time.time()
            elif time.time() - last > quiet:
                return True
        return True

    alive = settle()
    for a in answers:
        if not alive:
            break
        os.write(fd, (a + "\r").encode())
        alive = settle()
    try:
        os.kill(pid, 9)
        os.waitpid(pid, 0)
    except OSError:
        pass
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", out.decode("utf-8", "replace"))


BAD_OUTPUT = ["unbound variable", "command not found", "syntax error", "Could not extract", "key path"]


@pytest.mark.parametrize("args,answers,expect", [
    (["clean"], ["p"], "Preview only"),
    (["mac"], [], "Hidden caches you can clear"),
    (["protect"], ["n"], "System Integrity Protection"),
    (["perf"], [], "Busiest apps"),
    (["check"], ["n", "n"], "What to do"),
    ([], ["2", "", "q"], "This Mac"),
])
def test_tty_every_screen(tmp_path, args, answers, expect):
    (tmp_path / "Downloads").mkdir()
    cache = make_cache(tmp_path)
    text = run_tty(tmp_path, ["--no-color", *args], answers)
    for bad in BAD_OUTPUT:
        assert bad not in text, bad
    assert expect in text
    assert (cache / "blob.bin").exists()  # nothing here moves files
    if args == ["check"]:
        assert "Battery health" in text or "SSD health" in text
        assert list((tmp_path / "Downloads").glob("MacUp-Health-Report-*.pdf"))


@pytest.mark.parametrize("code", ["ro", "ko"])
def test_tty_complete_check_in_other_languages(tmp_path, code):
    (tmp_path / "Downloads").mkdir()
    text = run_tty(tmp_path, ["--no-color", "--lang", code, "check"], ["n", "n"])
    for bad in BAD_OUTPUT:
        assert bad not in text, bad
    assert lang_strings(code)["S_battery_health"] in text or lang_strings(code)["S_part_ssd"] in text
    assert list((tmp_path / "Downloads").glob("MacUp-Health-Report-*.pdf"))


# ── 6 · Recent Items ─────────────────────────────────────────────────────

def test_recent_helper_is_universal_signed_and_counts():
    helper = ROOT / "bin" / "macup-recent"
    archs = subprocess.run(["lipo", "-archs", str(helper)], capture_output=True, text=True).stdout.split()
    assert sorted(archs) == ["arm64", "x86_64"]
    sig = subprocess.run(["codesign", "-dv", str(helper)], capture_output=True, text=True).stderr
    assert "Signature=adhoc" in sig
    out = subprocess.run([str(helper), "count"], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0
    assert re.fullmatch(r"\d+ \d+ \d+", out.stdout.strip())  # read-only call


def fake_recent_tree(tmp_path):
    """A copy of MacUp whose Recent Items helper only pretends (never touches the real list)."""
    import shutil
    tree = tmp_path / "macup-copy"
    tree.mkdir()
    for part in ["macup", "VERSION", "lib", "engine"]:
        src = ROOT / part
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, tree / part)
    (tree / "bin").mkdir()
    state = tmp_path / "recent-state"
    state.write_text("4 2 1")
    (tree / "bin" / "macup-recent").write_text(
        f'#!/bin/bash\ncase "$1" in count) cat "{state}" ;; clear) echo "0 0 0" > "{state}"; cat "{state}" ;; esac\n')
    (tree / "bin" / "macup-recent").chmod(0o755)
    return tree, state


def test_recent_items_cleared_only_after_yes(tmp_path):
    tree, state = fake_recent_tree(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    global MACUP
    real = MACUP
    MACUP = tree / "macup"
    try:
        text = run_tty(home, ["--no-color", "recent"], ["n"])
        assert "Cancelled" in text and state.read_text().strip() == "4 2 1"
        text = run_tty(home, ["--no-color", "recent"], ["y"])
    finally:
        MACUP = real
    for bad in BAD_OUTPUT:
        assert bad not in text, bad
    assert "Applications" in text and "Recent Items cleared" in text
    assert state.read_text().strip() == "0 0 0"


def test_recent_items_never_cleared_without_a_terminal(tmp_path):
    tree, state = fake_recent_tree(tmp_path)
    out = run([str(tree / "macup"), "--no-color", "recent"], tmp_path)
    assert out.returncode == 0, out.stderr
    assert state.read_text().strip() == "4 2 1"
