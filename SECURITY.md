# Security

## What MacUp can and cannot do

- Runs as your user. It never asks for an admin password and refuses to install with `sudo`.
- Cleaning only **moves files to the Trash** (`~/.Trash`). It never empties the Trash.
- The checks (This Mac, Protection, Performance, Complete check) are read-only.
- No background process, no telemetry. The only network access is `macup update`
  and the installer, which download this repository from GitHub over HTTPS.
- Installs only into `~/.macup` plus one `macup` link. The installer refuses to
  replace a `~/.macup` folder or a `macup` command that isn’t MacUp.

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
