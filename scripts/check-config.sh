#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

fail=0
for f in auto/config config/package-lists/cfos-base.list.chroot config/includes.chroot/etc/greetd/config.toml; do
  if [[ ! -s "$f" ]]; then echo "FAIL: missing/empty $f"; fail=1; else echo "OK: $f"; fi
done

if grep -Eq '^ +[^#[:space:]]' config/package-lists/cfos-base.list.chroot; then
  echo "FAIL: package list contains blank/indented entries"
  fail=1
fi

if ! grep -qx 'live-boot' config/package-lists/cfos-base.list.chroot; then
  echo "FAIL: live-boot package missing"
  fail=1
fi

if ! grep -qx 'cups' config/package-lists/cfos-base.list.chroot; then
  echo "FAIL: CUPS package missing"
  fail=1
fi

if [[ "$fail" -eq 0 ]]; then echo "Configuration checks passed."; else exit 1; fi
