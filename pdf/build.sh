#!/bin/bash
# Builds bin/macup-pdf (Apple silicon + Intel, macOS 13+) from pdf/MacUpPDF.swift.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
for arch in arm64 x86_64; do
  xcrun swiftc -O -target "$arch-apple-macos13.0" -o "$TMP/macup-pdf-$arch" "$ROOT/pdf/MacUpPDF.swift"
done
mkdir -p "$ROOT/bin"
lipo -create -output "$ROOT/bin/macup-pdf" "$TMP/macup-pdf-arm64" "$TMP/macup-pdf-x86_64"
codesign --force --sign - "$ROOT/bin/macup-pdf"
lipo -info "$ROOT/bin/macup-pdf"
