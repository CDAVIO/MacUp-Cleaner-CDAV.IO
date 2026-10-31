#!/bin/bash
# Builds bin/macup-recent (Apple silicon + Intel, macOS 13+) from recent/MacUpRecent.swift.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
for arch in arm64 x86_64; do
  xcrun swiftc -O -suppress-warnings -target "$arch-apple-macos13.0" -o "$TMP/macup-recent-$arch" "$ROOT/recent/MacUpRecent.swift"
done
mkdir -p "$ROOT/bin"
lipo -create -output "$ROOT/bin/macup-recent" "$TMP/macup-recent-arm64" "$TMP/macup-recent-x86_64"
codesign --force --sign - "$ROOT/bin/macup-recent"
lipo -info "$ROOT/bin/macup-recent"
