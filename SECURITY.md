# Security

## What MacUp can and cannot do

- Runs as your user. It never asks for an admin password and refuses to install with `sudo`.
- Cleaning only **moves files to the Trash** (`~/.Trash`). It never empties the Trash.
- The checks (This Mac, Protection, Performance, Complete check, Wi-Fi Fix) are read-only.
- Wi-Fi Fix never changes a setting by itself. It writes down your current
  settings first, then opens System Settings or your router’s page so you can
  make the change; `macup wifi undo` shows what was there before.
- No background process, no telemetry. The only network access is `macup update`
  and the installer, which download this repository from GitHub over HTTPS, and
  `macup wifi`, which runs Apple’s built-in speed test (`networkQuality`) and
  pings your router and 1.1.1.1.
- Installs only into `~/.macup` plus one `macup` link. The installer refuses to
  replace a `~/.macup` folder or a `macup` command that isn’t MacUp.

## Fake copies

The only official MacUp is <https://github.com/CDAVIO/MacUp-Cleaner-CDAV.IO>,
installed with the one line in the README. MacUp is **free**: it never asks for
money, an account, a licence key or your admin password. A “MacUp” that does is
not ours — don’t install it, and please report it (see below and
[TRADEMARKS.md](TRADEMARKS.md)).

## Reporting a problem

Please open a [GitHub issue](https://github.com/CDAVIO/MacUp-Cleaner-CDAV.IO/issues)
for bugs. For anything that could put users’ files at risk, use
[private vulnerability reporting](https://github.com/CDAVIO/MacUp-Cleaner-CDAV.IO/security/advisories/new)
instead of a public issue, and include:

- your macOS version and Mac model,
- the exact command you ran,
- what happened and what you expected.

The operation log at `~/.cache/apple-cleanup/operations.log` lists every item
MacUp moved to the Trash and where it went — it helps a lot.
