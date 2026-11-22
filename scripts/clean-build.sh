#!/bin/bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: run with sudo/root: sudo ./scripts/clean-build.sh" >&2
  exit 1
fi
command -v lb >/dev/null 2>&1 || { echo "ERROR: live-build is not installed" >&2; exit 1; }
lb clean --purge
