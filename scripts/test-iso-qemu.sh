#!/bin/bash
# Optional smoke test. On CPUs without VT-x (e.g. Pentium E5700) this runs in slow software
# emulation: expect minutes to boot. Booting the ISO from USB on the real machine is the better test.
set -euo pipefail
ISO="${1:?usage: $0 path/to/image.iso}"
command -v qemu-system-x86_64 >/dev/null || { echo "Install qemu-system-x86" >&2; exit 1; }
ACCEL=(); [[ -r /dev/kvm && -w /dev/kvm ]] && ACCEL=(-enable-kvm) || echo "KVM unavailable: using slow software emulation" >&2
exec qemu-system-x86_64 "${ACCEL[@]}" -m 2048 -smp 2 -cdrom "$ISO" -boot d -vga std
