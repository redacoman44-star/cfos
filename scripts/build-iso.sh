#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run this script with sudo/root: sudo ./scripts/build-iso.sh" >&2
  exit 1
fi

if ! command -v lb >/dev/null 2>&1; then
  echo "ERROR: live-build is missing. Install it with: apt install live-build" >&2
  exit 1
fi

if [[ "$(dpkg --print-architecture 2>/dev/null || true)" != "amd64" ]]; then
  echo "WARNING: this configuration targets amd64; build host architecture differs." >&2
fi

chmod +x auto/config config/hooks/normal/*.hook.chroot
lb config
lb build 2>&1 | tee build.log; test "${PIPESTATUS[0]}" -eq 0

echo
echo "Build finished. Look for the generated *.iso file in: $PROJECT_DIR"
