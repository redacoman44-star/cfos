# CFOS Core v0.4

CFOS Core provides lightweight host diagnostics, USB inventory, cooperative
reservations, udev event history, and guarded opt-in USB passthrough to
libvirt/QEMU Windows guests.

## Commands

```sh
cfos status
cfos resources
cfos devices
cfos sessions
cfos events
cfos reserve --device 1-2 --owner windows-vm
cfos release --device 1-2 --owner windows-vm
sudo cfos passthrough --local --device 1-2 --domain windows-maintenance
sudo cfos unpassthrough --local --device 1-2 --domain windows-maintenance
```

Passthrough requires optional libvirt/QEMU host packages, root privileges, a
running domain, and an approved USB interface class. It is intentionally
local-only and is not exposed through the privileged daemon socket. See
`docs/CORE_V0.4.md` for dependencies, safety policy, and limitations.

## Tests

```sh
PYTHONPATH=core python3 -m unittest discover -s core/tests -v
```

The tests mock libvirt and sysfs-facing operations; they do not replace physical
hardware validation on Debian 13.


## Driver Intelligence v0.6.1
(v0.7 adds approval-gated installation: see docs/CORE_V0.7.md)

Use `cfos drivers --local` for a system report or `cfos driver --device <USB_SYSFS_ID|PCI_BDF> --local` for one device. This is read-only; package/module changes are not performed. See `docs/CORE_V0.6.md`.
