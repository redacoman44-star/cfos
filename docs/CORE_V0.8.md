# CFOS Core v0.8 — USB lifecycle and recovery

## New commands (local only)
```sh
cfos usb-reconcile --local [--json]      # read-only: compare reservations, devices and libvirt state
sudo cfos usb-recover --local [--json]   # release only provably stale CFOS reservations
```

## Reservation states
| State | Meaning | Fixed by `usb-recover` |
|---|---|---|
| `active` | Device is attached to the running domain | no |
| `reserved_for_persistent` | Domain stopped, device is in its persistent definition | no |
| `device_missing` | Device unplugged | yes |
| `domain_missing` | `qemu:<domain>` is not defined in libvirt | yes |
| `attach_missing` | Domain running but device not attached | yes |
| `owner_not_running` | Domain stopped, device not in its definition | yes |
| `unverifiable` | libvirt unavailable / domain XML unreadable | no |
| `foreign_owner` | Owner is not `qemu:*` | never |

Orphans (device attached to a running domain with no CFOS reservation) are reported with a
suggested command; recovery never detaches devices or edits domain definitions.
Each release is written to the audit log (`usb_recover_release`).

## Passthrough hardening (runtime_manager)
- Persistent (`--config`) changes now use vendor/product IDs, not bus/device numbers, which change on
  every replug/reboot. Live changes still use the exact current address. Persistent mode is refused when
  several identical devices (same vendor/product) are connected.
- If `attach-device --live` returns an error, CFOS checks libvirt: the reservation is released only when
  the device is confirmed not attached. If it is attached or the state cannot be verified, the
  reservation is kept and `usb-reconcile` is suggested.
- If the live attach succeeds but the persistent update fails, the reservation is kept and the error says so.

## Limitations
- Validated with mocks and a fake `virsh`; real libvirt/QEMU and USB hardware behaviour still needs
  testing on Debian 13 (see tests/ACCEPTANCE.md).
- No automatic hotplug handling (reservations are reconciled on demand, not on udev events) and no
  detach/cleanup of stale libvirt hostdev entries.
- Waydroid USB handling is not covered.
