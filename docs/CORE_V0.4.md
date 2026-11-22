# CFOS Core v0.4 — guarded USB runtime integration

## Scope

v0.4 adds an explicit USB passthrough adapter for libvirt/QEMU. It is opt-in,
requires root, and is invoked locally (`--local`) rather than through the
privileged CFOS daemon socket. This keeps VM-control operations outside the
socket API until polkit authorization and a per-user policy layer exist.

## Optional host packages

Install only on machines that will run Windows guests:

```sh
sudo apt install --yes qemu-system-x86 libvirt-daemon-system libvirt-clients
sudo systemctl enable --now libvirtd
```

A working KVM-capable CPU/firmware setup and a configured libvirt domain are
also required. These packages are intentionally not part of the lightweight
base image package list.

## Attach a USB printer/scanner to a running VM

```sh
cfos devices
sudo cfos passthrough --local --device 1-2 --domain windows-maintenance
```

To also update the persistent domain definition:

```sh
sudo cfos passthrough --local --device 1-2 --domain windows-maintenance --persistent
```

Detach and return the device to the host:

```sh
sudo cfos unpassthrough --local --device 1-2 --domain windows-maintenance
```

`--device` is the sysfs name shown by `cfos devices`. The implementation uses
the current USB bus/device address, not VID/PID alone, to avoid selecting a
different identical device. The VM must already be running for live attach.

## Safety policy

- Default allowlist: USB interface classes `06` (imaging) and `07` (printer).
- HID (`03`), hubs (`09`), mass storage (`08`), unknown classes, and mixed
  allowed/disallowed interface sets are blocked.
- Vendor-specific (`ff`) devices require explicit `--allow-vendor-specific`.
  Use this only after verifying the exact device; it may expose non-printer
  functions.
- libvirt `managed='yes'` handles host driver detach/reattach where supported.
- CFOS creates an advisory reservation `qemu:<domain>` before attach and rolls
  it back if attach fails. Detach releases it only after libvirt succeeds.
- Commands are passed as an argv list; no shell is invoked.
- Passthrough is not available through the root daemon socket. Use sudo for
  the local CLI operation.

## Limitations

- Physical detach/reattach behavior depends on the device, host driver, libvirt,
  kernel and guest OS; validate on target hardware.
- Some printers/scanners expose vendor-specific interfaces and will require
  explicit opt-in. Some multifunction devices expose several interfaces and
  are deliberately blocked by the conservative default policy.
- This release does not implement Waydroid USB passthrough, hotplug policy
  automation, polkit, or a graphical device handoff UI.
- Do not passthrough the host's keyboard, mouse, root hub, boot storage, or any
  device needed to keep the host usable.
