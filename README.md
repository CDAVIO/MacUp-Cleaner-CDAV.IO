# ✦ MacUp

**Mac health from the Terminal — free & open source.**
Find the hidden caches behind “System Data”, check your SSD, battery, memory,
processor, graphics and built-in security, and get a one-page **Mac health %**
with a PDF report saved in Downloads.

No app to download, no account, no subscription, no admin password.
MacUp **never deletes anything for good** — everything it cleans goes to the Trash.

🌐 [macup.cdav.io](https://macup.cdav.io) · English · Română · Deutsch · Italiano · Français · 한국어 · 中文

---

## Install (one line)

Open **Terminal** (⌘ Space → type “Terminal” → Enter) and paste:

```bash
curl -fsSL https://raw.githubusercontent.com/CDAVIO/MacUp-Cleaner-CDAV.IO/main/install.sh | bash
```

Then type:

```bash
macup
```

Needs macOS 13 Ventura or newer (Apple silicon or Intel). The installer copies
MacUp into `~/.macup` and adds the `macup` command — nothing runs in the
background and nothing is sent anywhere. Read [`install.sh`](install.sh) first if
you like; it is short.

---

## What it does

```
  ✦ MacUp  Mac health from the Terminal · free & open source
  ──────────────────────────────────────────────────────────────
   1  Smart Clean      Find hidden caches and move them to the Trash
   2  This Mac         Storage, SSD, battery, memory, processor, graphics
   3  Protection       Is macOS’s built-in security switched on?
   4  Performance      Load, busiest apps, startup items
   5  Complete check   Everything + Mac health % + PDF report in Downloads
```

| # | Command | What you get |
|---|---------|--------------|
| 1 | `macup clean` | Scans app caches, browser caches, logs, crash reports and developer caches (Xcode, npm, pip, Homebrew…). Shows sizes first. Press **Enter** to move the selected ones to the Trash, **p** to preview, numbers to select/unselect. |
| 2 | `macup mac` | Storage used/free, hidden caches, **SSD** model + S.M.A.R.T. status (+ life left % if `smartmontools` is installed), **battery** health %, cycle count, condition and charge, **RAM** free + swap, **processor** cores, load and heat, **graphics** and displays. |
| 3 | `macup protect` | Gatekeeper, System Integrity Protection, FileVault, Firewall, XProtect, security responses and automatic updates — on or off, and where to switch them on. |
| 4 | `macup perf` | Load, busiest apps (processor and memory), startup items and broken startup items. |
| 5 | `macup check` | Runs everything (read-only), gives your Mac a **health %** and saves `MacUp-Health-Report-….pdf` in **Downloads**. |

Other commands: `macup update`, `macup uninstall`, `macup --lang ro|de|it|fr|ko|zh`,
`macup --help`. The language follows your Mac automatically.

### Example: complete check

```
  5  Complete check
  ──────────────────────────────────────────────────────────────
  Mac health               ███████████████████░░░░░   79%  Good

  Storage                  ████████░░░░░░░░░░░░░░░░   36%
  SSD health               ████████████████████████  100%
  Battery                  ██████████████████████░░   93%
  Memory (RAM)             ███████████████████░░░░░   80%
  Processor                ████████████████░░░░░░░░   70%
  Protection               ████████████████████████  100%
  Hidden caches            ███████████████████░░░░░   85%

  →  What to do
  ✕  Low disk space (6% free)
     Below 15% free, macOS slows down. Clear hidden caches first, then empty the Trash.
     $ macup clean
  !  Memory is under pressure
     macOS is using 19 GB of swap. Quit apps and browser tabs you don’t need, or restart.

  ✓ PDF report saved:
     ~/Downloads/MacUp-Health-Report-2026-10-31-1720.pdf
```

The PDF has three A4 pages: the health ring with six score tiles, every detail
(storage, SSD, battery, memory, processor, graphics, security), and a numbered
“What to do” list.

**How the health % is made:** storage 20 · SSD 15 · battery 15 · memory 15 ·
security 15 · processor 10 · hidden caches 10. Parts your Mac doesn’t have
(e.g. a battery on an iMac) are left out. 90 %+ Excellent · 75 %+ Good · 55 %+ Fair.

---

## “System Data” is mostly hidden cache — no need to format or reset

macOS keeps caches, logs and crash reports in hidden folders such as
`~/Library/Caches` and `~/Library/Logs`. Over months they can grow to many
gigabytes and show up in Settings as **System Data**. Apps rebuild these files
by themselves, so clearing them is safe. You do **not** need to format or reset
your Mac to get that space back — `macup clean` does it, and everything goes
to the Trash first so you can put it back.

## Do Macs need a paid antivirus or “virus cleaner”?

For most people, no. Every Mac already includes free protection: **XProtect**
(Apple’s malware scanner, updated automatically), **Gatekeeper** (checks apps
before they open), **System Integrity Protection** and automatic **security
responses**. A yearly “clean viruses from your Mac” subscription does not make
these stronger. Pop-ups that say “your Mac is infected” are scams.

What actually keeps a Mac safe: keep macOS updated, install apps from the App
Store or developers you trust, and keep FileVault and the firewall on —
`macup protect` shows all of this in one screen.

## How MacUp compares

| | **MacUp** | Subscription cleaner apps | “Mac antivirus” subscriptions | Doing it by hand |
|---|---|---|---|---|
| Price | **Free, open source** | Yearly subscription | Yearly subscription | Free |
| Updates included | **Yes, forever** (`macup update`) | While you pay | While you pay | — |
| Account required | **No** | Usually | Usually | No |
| Shows everything before removing | **Yes** (sizes + preview) | Varies | — | You decide |
| Moves to Trash (undo) | **Always** | Varies | — | Easy to delete for good by mistake |
| Developer caches (Xcode, npm, Cargo…) | **30+ tools** | Some | No | Hard to find |
| Health report (SSD, battery, RAM, CPU, GPU) | **Yes + PDF** | Varies | No | Many different places |
| Works offline, no telemetry | **Yes** | Varies | No (cloud scanning) | Yes |
| Malware scanning | No — macOS does it (XProtect) | Some | Yes | No |
| Uses scare tactics | **Never** | Sometimes | Sometimes | — |

---

## Safety

- **Trash only.** The cleaning engine runs in Trash-only mode; MacUp never
  empties the Trash and never deletes files for good.
- **Only caches that rebuild themselves.** Developer cleanup is an allowlist of
  download/build caches. Never offered: commands that delete for good (Docker
  prune, simulator deletes, `brew cleanup`), downloaded AI models, Xcode
  Archives, the Maven local repository and the live system font cache.
- **Read-only checks.** Options 2–5 only read information. They don’t change
  settings; when something is off, MacUp tells you where to switch it on.
- **No admin password, no background process, no network** (except
  `macup update`, which downloads from this GitHub repo).
- **Skips files in use.** Files an app is using right now are left alone.
- See [SECURITY.md](SECURITY.md) to report a problem.

## Uninstall

```bash
macup uninstall
```

This removes `~/.macup` and the `macup` command. Your PDF reports stay in Downloads.

## SSD life %

macOS only reports S.M.A.R.T. *Verified / Failing*. To see the SSD’s remaining
life %, install the free [smartmontools](https://www.smartmontools.org) once —
MacUp picks it up automatically:

```bash
brew install smartmontools
```

## For developers

```
macup            entry point (Bash 3.2 — works with the bash that ships with macOS)
lib/             ui.sh · i18n.sh · checks.sh · clean.sh · views.sh · report.sh
lib/lang/        en ro de it fr ko zh (English is the fallback for any missing text)
engine/          cleanup engine (clean_mac.sh + lib/), used in Trash-only mode
pdf/             MacUpPDF.swift — turns the HTML report into a PDF (WebKit + PDFKit)
bin/macup-pdf    universal build of pdf/ (pdf/build.sh rebuilds it)
tests/           pytest suite
install.sh       installer
```

Run the tests:

```bash
python3 -m venv .venv && .venv/bin/pip install pytest && .venv/bin/python -m pytest -q
```

Only built-in macOS tools are used (`system_profiler`, `diskutil`, `sysctl`,
`memory_pressure`, `pmset`, `spctl`, `csrutil`, `fdesetup`, `plutil`…).

## License

MIT — see [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
MacUp is not affiliated with Apple Inc. Made by [cdav.io](https://cdav.io).
