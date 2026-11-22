#!/bin/bash
# Verify every package in config/package-lists/*.list.chroot exists in the host's APT sources.
# Run on Debian 13 (or the debian:trixie container) after `apt-get update`.
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
missing=0; total=0
while read -r pkg; do
  total=$((total+1))
  out="$(apt-cache policy "$pkg" 2>/dev/null || true)"
  if [[ -z "$out" ]] || grep -q 'Candidate: (none)' <<<"$out"; then
    echo "MISSING: $pkg"; missing=$((missing+1))
  fi
done < <(cat config/package-lists/*.list.chroot | sed 's/#.*//' | tr -s '[:space:]' '\n' | grep -v '^$' | sort -u)
echo "Checked $total packages; missing: $missing"
[[ "$missing" -eq 0 ]] || { echo "Fix config/package-lists before building." >&2; exit 1; }
